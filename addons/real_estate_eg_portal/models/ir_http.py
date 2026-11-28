import logging

from werkzeug.datastructures import WWWAuthenticate
from werkzeug.exceptions import Forbidden, HTTPException, Unauthorized

from odoo import models
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError
from odoo.http import SessionExpiredException, request

_logger = logging.getLogger(__name__)

# BR-58: every path of the customer API.
API_PREFIX = "/api/v1/"
# BR-59: the header that carries the CSRF token of a browser session.
CSRF_HEADER = "X-CSRF-Token"
# BR-59: methods that change nothing, allowed with the session alone. Not
# OPTIONS: Odoo adds it to every route and, without CORS, sends it to the
# endpoint like any other method.
SAFE_METHODS = ("GET", "HEAD")


class CsrfError(Forbidden):
    """BR-59: a browser call that changes data without a valid CSRF token.
    An HTTPException, so Odoo does not log it as a warning."""


def json_error(status, code, message, headers=None):
    """BR-58: the one error shape of the API."""
    return request.make_json_response(
        {"error": {"code": code, "message": message}},
        headers=headers,
        status=status,
    )


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _auth_method_re_portal_api(cls):
        """BR-55 / BR-59: the authentication of every /api/v1/ endpoint.

        - A request with an ``Authorization`` header is checked exactly as
          Odoo's ``auth="bearer"`` (an API key, BR-55). Nothing changes for
          the clients of Story 12.
        - Otherwise the browser session of the logged-in user is used, so the
          portal screens can call the API with ``fetch()``. A method that
          changes data (POST) must also carry the session's CSRF token in the
          ``X-CSRF-Token`` header: another site can make the browser send the
          session cookie, but it cannot read the token from our pages.

        Odoo's own bearer method accepts a session only for a top-level page
        navigation (``Sec-Fetch-*`` headers), never for ``fetch()``, which is
        why this method exists (Story 13, Option A).
        """
        httprequest = request.httprequest
        if "Authorization" in httprequest.headers:
            return cls._auth_method_bearer()
        if not request.env.uid or request.env.uid in cls._get_public_users():
            raise Unauthorized(
                "Log in, or send an API key: Authorization: Bearer <key>.",
                www_authenticate=WWWAuthenticate("bearer"),
            )
        if httprequest.method not in SAFE_METHODS and not request.validate_csrf(
            httprequest.headers.get(CSRF_HEADER)
        ):
            raise CsrfError()
        cls._auth_method_user()

    @classmethod
    def _handle_error(cls, exception):
        """BR-58: an error on an API path is answered in JSON with its HTTP
        code, never with an HTML page or a traceback. Errors the controllers
        expect are answered by the controllers themselves; this covers what
        happens around them: authentication (401), unknown paths (404) and
        bugs (500)."""
        if not request or not request.httprequest.path.startswith(API_PREFIX):
            return super()._handle_error(exception)
        env = request.env
        if isinstance(exception, CsrfError):
            return json_error(
                403,
                "csrf_failed",
                env._("Missing or invalid CSRF token: reload the page and try again."),
            )
        if isinstance(exception, (SessionExpiredException, AccessDenied)) or (
            isinstance(exception, HTTPException) and exception.code == 401
        ):
            if "Authorization" in request.httprequest.headers:
                message = env._("Send a valid API key: Authorization: Bearer <key>.")
            else:
                # BR-59: a browser whose session has expired.
                message = env._(
                    "You are not logged in or your session has expired: log in again."
                )
            return json_error(
                401,
                "unauthorized",
                message,
                headers=[("WWW-Authenticate", "Bearer")],
            )
        if isinstance(exception, HTTPException) and (exception.code or 0) >= 400:
            return json_error(
                exception.code,
                exception.name.lower().replace(" ", "_"),
                exception.name,
            )
        if isinstance(exception, MissingError):
            return json_error(404, "not_found", env._("Not found."))
        if isinstance(exception, AccessError):
            return json_error(403, "forbidden", env._("Access denied."))
        if isinstance(exception, UserError):
            return json_error(422, "validation_error", exception.args[0])
        if isinstance(exception, HTTPException):
            # Not an error (e.g. a redirect): Odoo's own answer.
            return super()._handle_error(exception)
        # A bug: Odoo logs the traceback; the client gets no detail.
        return json_error(500, "internal_error", env._("Internal server error."))
