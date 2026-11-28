"""AC-15.6: the OpenAPI 3 description of the customer API, served at
/api/v1/openapi.json. Kept by hand next to the controllers; the tests check
that every route of the API is listed here."""

PAGE_PARAMS = [
    {
        "name": "page",
        "in": "query",
        "schema": {"type": "integer", "minimum": 1, "default": 1},
    },
    {
        "name": "limit",
        "in": "query",
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
]

ERRORS = {
    code: {"$ref": f"#/components/responses/{name}"}
    for code, name in (
        ("400", "BadRequest"),
        ("401", "Unauthorized"),
        ("403", "Forbidden"),
        ("404", "NotFound"),
    )
}


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def _list(name, extra_params=()):
    return {
        "parameters": [*PAGE_PARAMS, *extra_params],
        "responses": {
            "200": {
                "description": "One page of the list.",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "data": {"type": "array", "items": _ref(name)},
                                "meta": _ref("Meta"),
                            },
                        }
                    }
                },
            },
            **ERRORS,
        },
    }


def _one(name, param):
    return {
        "parameters": [
            {
                "name": param,
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            }
        ],
        "responses": {
            "200": {
                "description": "The record.",
                "content": {"application/json": {"schema": _ref(name)}},
            },
            **ERRORS,
        },
    }


def _image(param, description, extra_params=()):
    """BR-61: an endpoint that answers an image, not JSON."""
    return {
        "parameters": [
            {
                "name": param,
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            },
            *extra_params,
        ],
        "responses": {
            "200": {
                "description": description,
                "content": {
                    "image/*": {"schema": {"type": "string", "format": "binary"}}
                },
            },
            **ERRORS,
        },
    }


def _query(name, schema):
    return {"name": name, "in": "query", "schema": schema}


def _error_response(description):
    return {
        "description": description,
        "content": {"application/json": {"schema": _ref("Error")}},
    }


REF = {
    "type": "object",
    "nullable": True,
    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
}
MONEY = {"type": "number"}


UNIT_PROPERTIES = {
    "id": {"type": "integer"},
    "code": {"type": "string"},
    "project": REF,
    "unit_type": {"type": "string"},
    "bedrooms": {"type": "integer"},
    "area": {"type": "number"},
    "floor": {"type": "integer"},
    "list_price": MONEY,
    "price_per_sqm": MONEY,
    "currency": {"type": "string"},
    "state": {"type": "string"},
    "image_url": {"type": "string", "nullable": True},
}


def openapi_spec():
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Real Estate Installments (Egypt): Customer API",
            "version": "1.0.0",
            "description": "US-15, US-16, US-17. For customers with a portal account. "
            "Authenticate with an Odoo API key: Authorization: Bearer <key>. "
            "The portal pages call the same API with the browser session "
            "instead; a POST then needs the page's CSRF token in the "
            "X-CSRF-Token header.",
        },
        "servers": [{"url": "/api/v1"}],
        "security": [{"bearer": []}, {"session": []}],
        "paths": {
            "/units": {
                "get": {
                    "summary": "Available units",
                    **_list(
                        "Unit",
                        [
                            _query("project_id", {"type": "integer"}),
                            _query("bedrooms", {"type": "integer", "minimum": 0}),
                            _query("unit_type", {"type": "string"}),
                        ],
                    ),
                }
            },
            "/units/{unit_id}": {
                "get": {
                    "summary": "One unit, with photos, floor plan, project and plans",
                    **_one("UnitDetails", "unit_id"),
                }
            },
            "/units/{unit_id}/floor-plan": {
                "get": {
                    "summary": "The unit's floor plan",
                    **_image("unit_id", "The floor plan image."),
                }
            },
            "/projects": {
                "get": {
                    "summary": "Projects with an available unit",
                    **_list("Project"),
                }
            },
            "/images/{image_id}": {
                "get": {
                    "summary": "One photo of a project or unit",
                    **_image(
                        "image_id",
                        "The photo.",
                        [
                            _query(
                                "size",
                                {
                                    "type": "string",
                                    "enum": ["128", "256", "512", "1024", "1920"],
                                    "default": "1024",
                                },
                            )
                        ],
                    ),
                }
            },
            "/reservations": {
                "get": {
                    "summary": "My reservations",
                    **_list("Reservation", [_query("state", {"type": "string"})]),
                },
                "post": {
                    "summary": "Request a reservation of an available unit",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": _ref("ReservationRequest")}
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "The request, state requested.",
                            "content": {
                                "application/json": {"schema": _ref("Reservation")}
                            },
                        },
                        **ERRORS,
                        "409": _error_response(
                            "Unit not available, duplicate request or too many "
                            "open requests."
                        ),
                        "422": _error_response("Invalid values."),
                    },
                },
            },
            "/reservations/{reservation_id}": {
                "get": {
                    "summary": "One of my reservations",
                    **_one("Reservation", "reservation_id"),
                }
            },
            "/contracts": {"get": {"summary": "My contracts", **_list("Contract")}},
            "/contracts/{contract_id}": {
                "get": {
                    "summary": "One of my contracts",
                    **_one("Contract", "contract_id"),
                }
            },
            "/installments": {
                "get": {
                    "summary": "The schedule lines of my contracts",
                    **_list(
                        "Installment",
                        [
                            _query("contract_id", {"type": "integer"}),
                            _query("overdue", {"type": "boolean"}),
                        ],
                    ),
                }
            },
        },
        "components": {
            "securitySchemes": {
                "bearer": {"type": "http", "scheme": "bearer"},
                # BR-59: the portal pages (Odoo's session cookie).
                "session": {"type": "apiKey", "in": "cookie", "name": "session_id"},
            },
            "responses": {
                "BadRequest": _error_response("Invalid parameter or body."),
                "Unauthorized": _error_response(
                    "Missing or invalid API key, and no logged-in session."
                ),
                "Forbidden": _error_response(
                    "Not a customer (portal) account, or a session POST "
                    "without a valid X-CSRF-Token header."
                ),
                "NotFound": _error_response("No such record among yours."),
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        }
                    },
                },
                "Meta": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "limit": {"type": "integer"},
                        "total": {"type": "integer"},
                    },
                },
                "Unit": {
                    "type": "object",
                    "properties": UNIT_PROPERTIES,
                },
                "UnitDetails": {
                    "type": "object",
                    "properties": {
                        **UNIT_PROPERTIES,
                        "images": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "caption": {
                                        "type": "string",
                                        "nullable": True,
                                    },
                                    "url": {"type": "string"},
                                    "thumbnail_url": {"type": "string"},
                                },
                            },
                        },
                        "floor_plan_url": {"type": "string", "nullable": True},
                        "plans": {
                            "type": "array",
                            "items": _ref("PlanPreview"),
                        },
                        "project": _ref("Project"),
                    },
                },
                "Project": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "location": {"type": "string", "nullable": True},
                        "expected_delivery_date": {
                            "type": "string",
                            "format": "date",
                            "nullable": True,
                        },
                        "reservation_amount": MONEY,
                        "currency": {"type": "string"},
                        "description": {
                            "type": "string",
                            "nullable": True,
                            "description": "Sanitized HTML.",
                        },
                        "image_url": {"type": "string", "nullable": True},
                        "available_units": {
                            "type": "integer",
                            "description": "In the /projects list only.",
                        },
                    },
                },
                "PlanPreview": {
                    "type": "object",
                    "description": "BR-62: a plan worked out on the unit's price, "
                    "as the schedule of a contract signed today.",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "down_payment_percent": {"type": "number"},
                        "down_payment": MONEY,
                        "installment_count": {"type": "integer"},
                        "frequency": {
                            "type": "string",
                            "nullable": True,
                            "enum": ["monthly", "quarterly", "semi_annual", "annual"],
                        },
                        "installment_amount": MONEY,
                        "last_installment_amount": MONEY,
                        "first_installment_months": {
                            "type": "integer",
                            "nullable": True,
                        },
                        "maintenance_percent": {"type": "number"},
                        "maintenance": MONEY,
                        "maintenance_due": {
                            "type": "string",
                            "nullable": True,
                            "enum": ["signing", "delivery"],
                        },
                        "total": MONEY,
                    },
                },
                "ReservationRequest": {
                    "type": "object",
                    "required": ["unit_id"],
                    "properties": {
                        "unit_id": {"type": "integer"},
                        "note": {"type": "string", "maxLength": 2000},
                        "nationality": {
                            "type": "string",
                            "enum": ["egyptian", "foreign"],
                        },
                        "national_id": {"type": "string", "pattern": "^[23][0-9]{13}$"},
                        "passport_number": {"type": "string", "maxLength": 32},
                    },
                },
                "Reservation": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "reference": {"type": "string"},
                        "state": {
                            "type": "string",
                            "enum": [
                                "requested",
                                "agent_confirmed",
                                "reserved",
                                "converted",
                                "rejected",
                                "expired",
                            ],
                        },
                        "unit": REF,
                        "project": REF,
                        "amount": MONEY,
                        "currency": {"type": "string"},
                        "hold_until": {
                            "type": "string",
                            "format": "date",
                            "nullable": True,
                        },
                        "contract_id": {"type": "integer", "nullable": True},
                        "requested_on": {"type": "string", "format": "date-time"},
                    },
                },
                "Contract": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "reference": {"type": "string"},
                        "state": {"type": "string"},
                        "date": {"type": "string", "format": "date", "nullable": True},
                        "unit": REF,
                        "project": REF,
                        "price": MONEY,
                        "amount_paid": MONEY,
                        "amount_outstanding": MONEY,
                        "currency": {"type": "string"},
                    },
                },
                "Installment": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "contract": REF,
                        "label": {"type": "string"},
                        "line_type": {"type": "string"},
                        "number": {"type": "integer"},
                        "date_due": {
                            "type": "string",
                            "format": "date",
                            "nullable": True,
                        },
                        "amount": MONEY,
                        "amount_paid": MONEY,
                        "amount_residual": MONEY,
                        "state": {"type": "string"},
                        "is_overdue": {"type": "boolean"},
                        "currency": {"type": "string"},
                    },
                },
            },
        },
    }
