import logging

from werkzeug.exceptions import HTTPException

from odoo import models
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError
from odoo.http import SessionExpiredException, request

_logger = logging.getLogger(__name__)

# BR-58: every path of the customer API.
API_PREFIX = "/api/v1/"


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
    def _handle_error(cls, exception):
        """BR-58: an error on an API path is answered in JSON with its HTTP
        code, never with an HTML page or a traceback. Errors the controllers
        expect are answered by the controllers themselves; this covers what
        happens around them: authentication (401), unknown paths (404) and
        bugs (500)."""
        if not request or not request.httprequest.path.startswith(API_PREFIX):
            return super()._handle_error(exception)
        env = request.env
        if isinstance(exception, (SessionExpiredException, AccessDenied)) or (
            isinstance(exception, HTTPException) and exception.code == 401
        ):
            return json_error(
                401,
                "unauthorized",
                env._("Send a valid API key: Authorization: Bearer <key>."),
                headers=[("WWW-Authenticate", "Bearer")],
            )
        if isinstance(exception, HTTPException) and exception.code:
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
        # A bug: Odoo logs the traceback; the client gets no detail.
        return json_error(500, "internal_error", env._("Internal server error."))
