"""US-15: the customer portal REST API (BR-55 to BR-58).

Every endpoint is ``auth="re_portal_api"`` (models/ir_http.py): with an
``Authorization: Bearer <key>`` header, Odoo checks the API key and runs the
request as its owner, exactly as ``auth="bearer"`` (BR-55); without it, the
logged-in user's browser session is used, with the CSRF token in a header for
POST, so the portal screens can call the same API (BR-59). The caller must
be a portal user (BR-55). Reads run as that user, so Odoo's access rights and
the portal record rules of this module decide what they see (BR-56); only the
creation of a request runs as superuser, because customers have no create
right on reservations (BR-57).
"""

import functools
import json

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.tools import SQL

from odoo.addons.real_estate_eg.models.real_estate_reservation import (
    RESERVATION_STATE,
)

from ..models.ir_http import API_PREFIX, json_error
from .openapi import openapi_spec

# BR-58: pagination.
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
# Far beyond any real list; a larger offset would overflow in the database.
MAX_PAGE = 10_000
# BR-57: the reservations that are still open for a customer.
OPEN_STATES = ("requested", "agent_confirmed", "reserved")
MAX_OPEN_REQUESTS = 5
NATIONALITIES = ("egyptian", "foreign")
MAX_TEXT = 2000
MAX_PASSPORT = 32
# BR-61: the photo sizes a client may ask for (image.mixin).
IMAGE_SIZES = ("128", "256", "512", "1024", "1920")


class ApiError(Exception):
    """An expected error, answered as BR-58 JSON by the endpoint itself."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def api_endpoint(func):
    """BR-55 / BR-58 around each endpoint: portal users only, and expected
    errors answered in JSON with their HTTP code. The endpoint runs in a
    savepoint, so a refused request leaves nothing behind. Errors are caught
    here, not left to Odoo, because Odoo logs a warning for each UserError
    that leaves a controller."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        env = request.env
        if not env.user._is_portal():
            return json_error(
                403,
                "forbidden",
                env._("This API is for customers with a portal account."),
            )
        try:
            with env.cr.savepoint():
                return func(self, *args, **kwargs)
        except ApiError as error:
            return json_error(error.status, error.code, error.message)
        except MissingError:
            return json_error(404, "not_found", env._("Not found."))
        except AccessError:
            # BR-58: a row the customer may not read is "not found", so the
            # answer does not tell them it exists.
            return json_error(404, "not_found", env._("Not found."))
        except UserError as error:
            # Business rules of real_estate_eg (e.g. BR-49), raised as
            # UserError / ValidationError with a message meant for users.
            return json_error(422, "validation_error", error.args[0])

    return wrapper


def _route(path, methods=("GET",)):
    return http.route(
        API_PREFIX + path,
        type="http",
        # BR-55 / BR-59: an API key, or the browser session + CSRF header.
        auth="re_portal_api",
        methods=list(methods),
        # Odoo's own check reads a csrf_token form field; the auth method
        # checks the X-CSRF-Token header of session calls instead (BR-59).
        csrf=False,
        save_session=False,
    )


class PortalApi(http.Controller):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _int(kwargs, name, default=None, minimum=1, maximum=None):
        """A positive integer query parameter, or a 400 error."""
        raw = kwargs.get(name)
        if raw in (None, ""):
            return default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = None
        if value is None or value < minimum or (maximum and value > maximum):
            raise ApiError(
                400,
                "bad_request",
                request.env._("Parameter %(name)s is not valid.", name=name),
            )
        return value

    @staticmethod
    def _choice(kwargs, name, choices):
        value = kwargs.get(name)
        if value in (None, ""):
            return None
        if value not in choices:
            raise ApiError(
                400,
                "bad_request",
                request.env._(
                    "Parameter %(name)s must be one of: %(choices)s.",
                    name=name,
                    choices=", ".join(choices),
                ),
            )
        return value

    def _page(self, model, domain, serialize, kwargs, order=None):
        """BR-58: one page of a list, as the current user (record rules apply)."""
        page = self._int(kwargs, "page", default=1, maximum=MAX_PAGE)
        limit = self._int(kwargs, "limit", default=DEFAULT_LIMIT, maximum=MAX_LIMIT)
        Model = request.env[model]
        records = Model.search(
            domain, offset=(page - 1) * limit, limit=limit, order=order
        )
        return request.make_json_response(
            {
                "data": [serialize(record) for record in records],
                "meta": {
                    "page": page,
                    "limit": limit,
                    "total": Model.search_count(domain),
                },
            }
        )

    @staticmethod
    def _one(model, record_id):
        """BR-56 / BR-58: a record the current user can read, else 404."""
        record = request.env[model].search([("id", "=", record_id)])
        if not record:
            raise ApiError(404, "not_found", request.env._("Not found."))
        return record

    @staticmethod
    def _json_body():
        try:
            body = json.loads(request.httprequest.get_data() or b"{}")
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise ApiError(
                400, "bad_request", request.env._("The body must be a JSON object.")
            )
        return body

    # ------------------------------------------------------------------
    # Serializers: what a customer is shown, field by field
    # ------------------------------------------------------------------

    @staticmethod
    def _ref(record, field="name"):
        return {"id": record.id, "name": record[field]} if record else None

    def _unit(self, unit):
        return {
            "id": unit.id,
            "code": unit.code,
            "project": self._ref(unit.project_id),
            "unit_type": unit.unit_type,
            "bedrooms": unit.bedrooms,
            "area": unit.area,
            "floor": unit.floor,
            "list_price": unit.list_price,
            "price_per_sqm": unit.price_per_sqm,
            "currency": unit.currency_id.name,
            "state": unit.state,
            # BR-61: the cover, the unit's first photo or its project's.
            "image_url": self._image_url(unit._portal_images()[:1]),
        }

    @staticmethod
    def _image_url(image, size="1024"):
        return f"{API_PREFIX}images/{image.id}?size={size}" if image else None

    def _unit_details(self, unit):
        """BR-61 / BR-62 / BR-63: everything the unit page shows, read as the
        customer."""
        project = unit.project_id
        plans = [
            preview
            for plan in project.plan_template_ids
            if (preview := plan._portal_preview(unit.list_price))
        ]
        return {
            **self._unit(unit),
            "images": [
                {
                    "id": image.id,
                    "caption": image.name or None,
                    "url": self._image_url(image),
                    "thumbnail_url": self._image_url(image, "256"),
                }
                for image in unit._portal_images()
            ],
            "floor_plan_url": (
                f"{API_PREFIX}units/{unit.id}/floor-plan" if unit.floor_plan else None
            ),
            "plans": plans,
            "project": self._project(project),
        }

    def _project(self, project):
        return {
            "id": project.id,
            "name": project.name,
            "location": project.location or None,
            "expected_delivery_date": project.expected_delivery_date or None,
            "reservation_amount": project.reservation_amount,
            "currency": project.currency_id.name,
            "description": project.portal_description or None,
            "image_url": self._image_url(project.image_ids[:1]),
        }

    def _image_response(self, record, field_name):
        """BR-61: a stored image of a record the customer may read."""
        if not record.with_context(bin_size=True)[field_name]:
            raise ApiError(404, "not_found", request.env._("Not found."))
        stream = request.env["ir.binary"]._get_image_stream_from(record, field_name)
        return stream.get_response()

    def _reservation(self, reservation):
        return {
            "id": reservation.id,
            "reference": reservation.name,
            "state": reservation.state,
            "unit": self._ref(reservation.unit_id, "code"),
            "project": self._ref(reservation.project_id),
            "amount": reservation.amount,
            "currency": reservation.currency_id.name,
            "hold_until": reservation.date_expiry,
            "contract_id": reservation.contract_id.id or None,
            "requested_on": reservation.create_date,
        }

    def _contract(self, contract):
        return {
            "id": contract.id,
            "reference": contract.name,
            "state": contract.state,
            "date": contract.date or None,
            "unit": self._ref(contract.unit_id, "code"),
            "project": self._ref(contract.project_id),
            "price": contract.price,
            "amount_paid": contract.amount_paid,
            "amount_outstanding": contract.amount_outstanding,
            "currency": contract.currency_id.name,
        }

    def _installment(self, line):
        return {
            "id": line.id,
            "contract": self._ref(line.contract_id),
            "label": line.name,
            "line_type": line.line_type,
            "number": line.number,
            "date_due": line.date_due or None,
            "amount": line.amount,
            "amount_paid": line.amount_paid,
            "amount_residual": line.amount_residual,
            "state": line.state,
            "is_overdue": line.is_overdue,
            "currency": line.currency_id.name,
        }

    # ------------------------------------------------------------------
    # Units (AC-15.1)
    # ------------------------------------------------------------------

    @_route("units")
    @api_endpoint
    def list_units(self, **kwargs):
        """BR-56: the available units, the customer's catalogue."""
        domain = [("state", "=", "available")]
        project_id = self._int(kwargs, "project_id")
        if project_id:
            domain.append(("project_id", "=", project_id))
        bedrooms = self._int(kwargs, "bedrooms", minimum=0)
        if bedrooms is not None:
            domain.append(("bedrooms", "=", bedrooms))
        unit_types = (
            request.env["real.estate.unit"]._fields["unit_type"].get_values(request.env)
        )
        unit_type = self._choice(kwargs, "unit_type", unit_types)
        if unit_type:
            domain.append(("unit_type", "=", unit_type))
        return self._page(
            "real.estate.unit", domain, self._unit, kwargs, order="project_id, code"
        )

    @_route("units/<int:unit_id>")
    @api_endpoint
    def get_unit(self, unit_id, **kwargs):
        """BR-63: one unit with its photos, floor plan, project and the
        project's payment plans worked out on its price."""
        return request.make_json_response(
            self._unit_details(self._one("real.estate.unit", unit_id))
        )

    @_route("units/<int:unit_id>/floor-plan")
    @api_endpoint
    def get_floor_plan(self, unit_id, **kwargs):
        """BR-61: the unit's floor plan image."""
        return self._image_response(
            self._one("real.estate.unit", unit_id), "floor_plan"
        )

    # ------------------------------------------------------------------
    # Projects and photos (US-17)
    # ------------------------------------------------------------------

    @_route("projects")
    @api_endpoint
    def list_projects(self, **kwargs):
        """BR-61: the projects that have an available unit, with their cover
        and how many units are available, for the portal's banners."""
        counts = dict(
            request.env["real.estate.unit"]._read_group(
                [("state", "=", "available")], ["project_id"], ["__count"]
            )
        )

        def serialize(project):
            return {**self._project(project), "available_units": counts[project]}

        return self._page(
            "real.estate.project",
            [("id", "in", [project.id for project in counts])],
            serialize,
            kwargs,
            order="name",
        )

    @_route("images/<int:image_id>")
    @api_endpoint
    def get_image(self, image_id, **kwargs):
        """BR-61: one photo, if the customer may see it (a unit's photo
        follows the unit rule)."""
        size = self._choice(kwargs, "size", IMAGE_SIZES) or "1024"
        return self._image_response(
            self._one("real.estate.image", image_id), f"image_{size}"
        )

    # ------------------------------------------------------------------
    # Reservations (AC-15.3, AC-15.4)
    # ------------------------------------------------------------------

    @_route("reservations")
    @api_endpoint
    def list_reservations(self, **kwargs):
        """BR-56: the customer's reservations; the record rule filters them."""
        domain = []
        state = self._choice(kwargs, "state", [s for s, _label in RESERVATION_STATE])
        if state:
            domain.append(("state", "=", state))
        return self._page("real.estate.reservation", domain, self._reservation, kwargs)

    @_route("reservations/<int:reservation_id>")
    @api_endpoint
    def get_reservation(self, reservation_id, **kwargs):
        return request.make_json_response(
            self._reservation(self._one("real.estate.reservation", reservation_id))
        )

    @_route("reservations", methods=("POST",))
    @api_endpoint
    def create_reservation(self, **kwargs):
        """BR-57 / AC-15.3: a reservation request for an available unit."""
        env = request.env
        body = self._json_body()
        values = self._request_values(body)
        unit_id = body.get("unit_id")
        if not isinstance(unit_id, int) or isinstance(unit_id, bool) or unit_id < 1:
            raise ApiError(
                400, "bad_request", env._("unit_id must be a positive integer.")
            )
        # As the customer: a unit they cannot see is "not found" (BR-56).
        unit = self._one("real.estate.unit", unit_id)
        if unit.state != "available":
            raise ApiError(
                409,
                "unit_not_available",
                env._("Unit %(unit)s is not available.", unit=unit.code),
            )
        customer = env.user.partner_id.commercial_partner_id
        # Two requests sent at the same moment: both write the customer's row
        # (a no-op update), so the second one fails with a serialization error
        # and Odoo replays it with fresh data, where it sees the first request.
        # A lock alone would not do: the transaction already read a snapshot.
        env.cr.execute(
            SQL(
                "UPDATE res_partner SET write_date = write_date WHERE id = %s",
                customer.id,
            )
        )
        Reservation = env["real.estate.reservation"]
        mine = [("partner_id", "child_of", customer.id), ("state", "in", OPEN_STATES)]
        if Reservation.search_count([*mine, ("unit_id", "=", unit.id)]):
            raise ApiError(
                409,
                "duplicate_request",
                env._("You already have an open reservation for this unit."),
            )
        if Reservation.search_count(mine) >= MAX_OPEN_REQUESTS:
            raise ApiError(
                409,
                "too_many_requests",
                env._(
                    "You already have %(count)s open reservations.",
                    count=MAX_OPEN_REQUESTS,
                ),
            )
        # The one sudo() of the API (BR-57): customers have no create right on
        # reservations. Only these values are written (as superuser create()
        # would accept any field, the dict is built here, never from the
        # body); the model's create()
        # still checks the unit (BR-49), assigns the project's agent and gives
        # them a to-do (BR-51). The customer is not made a follower, so the
        # staff chatter sends them no e-mail.
        reservation = (
            Reservation.sudo()
            .with_context(mail_create_nosubscribe=True)
            .create(
                {
                    **values,
                    "partner_id": customer.id,
                    "unit_id": unit.id,
                }
            )
        )
        # Read back as the customer, through the record rule.
        return request.make_json_response(
            self._reservation(Reservation.browse(reservation.id)), status=201
        )

    @staticmethod
    def _request_values(body):
        """BR-57: the note and the identity the customer may send. Anything
        else in the body is ignored."""
        env = request.env

        def text(name, limit):
            value = body.get(name)
            if value in (None, ""):
                return False
            if not isinstance(value, str) or len(value.strip()) > limit:
                raise ApiError(
                    422,
                    "validation_error",
                    env._(
                        "%(name)s must be a text of at most %(limit)s characters.",
                        name=name,
                        limit=limit,
                    ),
                )
            return value.strip()

        note = text("note", MAX_TEXT)
        nationality = body.get("nationality") or False
        national_id = text("national_id", 14)
        passport = text("passport_number", MAX_PASSPORT)
        if nationality and nationality not in NATIONALITIES:
            raise ApiError(
                422,
                "validation_error",
                env._("nationality must be egyptian or foreign."),
            )
        if (national_id or passport) and not nationality:
            raise ApiError(
                422,
                "validation_error",
                env._("Give the nationality with the identity number."),
            )
        if nationality == "egyptian":
            # BR-06: the same check as on the contact.
            if not national_id or not env["res.partner"]._is_valid_national_id(
                national_id
            ):
                raise ApiError(
                    422,
                    "validation_error",
                    env._("An Egyptian customer needs a valid 14-digit national ID."),
                )
            passport = False
        if nationality == "foreign":
            if not passport:
                raise ApiError(
                    422,
                    "validation_error",
                    env._("A foreign customer needs a passport number."),
                )
            national_id = False
        return {
            "note": note,
            "customer_nationality": nationality,
            "customer_national_id": national_id,
            "customer_passport_number": passport,
        }

    # ------------------------------------------------------------------
    # Contracts and installments (AC-15.4)
    # ------------------------------------------------------------------

    @_route("contracts")
    @api_endpoint
    def list_contracts(self, **kwargs):
        return self._page("real.estate.contract", [], self._contract, kwargs)

    @_route("contracts/<int:contract_id>")
    @api_endpoint
    def get_contract(self, contract_id, **kwargs):
        return request.make_json_response(
            self._contract(self._one("real.estate.contract", contract_id))
        )

    @_route("installments")
    @api_endpoint
    def list_installments(self, **kwargs):
        """The schedule lines of the customer's contracts, by due date."""
        domain = []
        contract_id = self._int(kwargs, "contract_id")
        if contract_id:
            # 404 for a contract that is not the customer's.
            self._one("real.estate.contract", contract_id)
            domain.append(("contract_id", "=", contract_id))
        if kwargs.get("overdue") in ("1", "true"):
            domain.append(("is_overdue", "=", True))
        return self._page(
            "real.estate.installment",
            domain,
            self._installment,
            kwargs,
            order="contract_id, date_due, sequence, id",
        )

    # ------------------------------------------------------------------
    # OpenAPI (AC-15.6)
    # ------------------------------------------------------------------

    @http.route(
        API_PREFIX + "openapi.json",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def openapi(self, **kwargs):
        """The API's description; public, it holds no data."""
        return request.make_json_response(openapi_spec())
