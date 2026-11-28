from odoo.tests import HttpCase, new_test_user, tagged

from ..controllers.openapi import openapi_spec

AGENT = "real_estate_eg.group_real_estate_agent"
# BR-06: a valid Egyptian national ID (born 15 January 1999).
NATIONAL_ID = "29901158800017"


@tagged("post_install", "-at_install")
class TestPortalApi(HttpCase):
    """US-15 (v1.1): the customer portal REST API. BR-55 to BR-58.

    Customers A and B are portal users with an API key each. Horizon New
    Cairo's agent is the agent below. Customer A has a draft contract on unit
    0101 with its schedule, customer B one on unit 0102; units 0201 and 0202
    are available."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = new_test_user(cls.env, login="re_api_agent", groups=AGENT)
        cls.customer_a = new_test_user(
            cls.env, login="re_api_customer_a", groups="base.group_portal"
        )
        cls.customer_b = new_test_user(
            cls.env, login="re_api_customer_b", groups="base.group_portal"
        )
        cls.key_a = cls._api_key(cls.customer_a)
        cls.key_b = cls._api_key(cls.customer_b)
        cls.key_agent = cls._api_key(cls.agent)

        cls.project = cls.env["real.estate.project"].create(
            {
                "name": "Horizon New Cairo",
                "code": "HNC",
                "user_id": cls.agent.id,
                "reservation_amount": 100_000,
            }
        )
        cls.unit_a, cls.unit_b, cls.unit_free, cls.unit_free_2 = cls.env[
            "real.estate.unit"
        ].create(
            [
                {
                    "code": code,
                    "project_id": cls.project.id,
                    "unit_type": "apartment",
                    "bedrooms": bedrooms,
                    "area": 125,
                    "list_price": 6_500_000,
                }
                for code, bedrooms in (
                    ("HNC-API-0101", 2),
                    ("HNC-API-0102", 2),
                    ("HNC-API-0201", 3),
                    ("HNC-API-0202", 2),
                )
            ]
        )
        plan = cls.env["real.estate.plan.template"].create(
            {
                "name": "Standard 8 years",
                "code": "API-STD-8Q",
                "down_payment_percent": 10,
                "installment_count": 32,
                "frequency": "quarterly",
                "first_installment_months": 3,
                "maintenance_percent": 8,
                "maintenance_due": "delivery",
            }
        )
        Contract = cls.env["real.estate.contract"]
        cls.contract_a = Contract.create(
            {
                "partner_id": cls.customer_a.partner_id.id,
                "unit_id": cls.unit_a.id,
                "user_id": cls.agent.id,
                "date": "2026-01-10",
            }
        )
        cls.contract_a._generate_schedule(plan)
        cls.contract_b = Contract.create(
            {
                "partner_id": cls.customer_b.partner_id.id,
                "unit_id": cls.unit_b.id,
                "user_id": cls.agent.id,
                "date": "2026-01-10",
            }
        )
        cls.contract_b._generate_schedule(plan)

    @classmethod
    def _api_key(cls, user):
        # As the user, in sudo so the key may have no expiry date (as an
        # administrator would create it for a customer).
        return (
            cls.env["res.users.apikeys"]
            .with_user(user)
            .sudo()
            ._generate(None, "test", None)
        )

    def _call(self, path, key=None, method="GET", json=None, params=None):
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        # The request runs on the test cursor: write what the test set up
        # first, and read fresh values after.
        self.env.flush_all()
        response = self.url_open(
            "/api/v1/" + path,
            method=method,
            json=json,
            params=params,
            headers=headers,
        )
        self.env.invalidate_all()
        return response

    def _error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertTrue(response.headers["Content-Type"].startswith("application/json"))
        self.assertEqual(response.json()["error"]["code"], code)

    def _request(self, key=None, **body):
        body.setdefault("unit_id", self.unit_free.id)
        return self._call("reservations", key or self.key_a, "POST", json=body)

    # AC-15.1

    def test_us_15_list_available_units(self):
        """AC-15.1: only available units, paginated."""
        response = self._call("units", self.key_a)
        self.assertEqual(response.status_code, 200, response.text)
        codes = {unit["code"] for unit in response.json()["data"]}
        self.assertIn("HNC-API-0201", codes)
        self.assertIn("HNC-API-0202", codes)
        # Units with a draft contract are reserved: not in the catalogue.
        self.assertNotIn("HNC-API-0101", codes)
        self.assertNotIn("HNC-API-0102", codes)

        page = self._call("units", self.key_a, params={"limit": 1, "page": 2}).json()
        self.assertEqual(len(page["data"]), 1)
        self.assertEqual(page["meta"]["page"], 2)
        self.assertGreaterEqual(page["meta"]["total"], 2)

        filtered = self._call(
            "units", self.key_a, params={"project_id": self.project.id, "bedrooms": 3}
        ).json()
        self.assertEqual([u["code"] for u in filtered["data"]], ["HNC-API-0201"])

    def test_ac_15_1_unit_on_hold_is_hidden(self):
        """BR-50: a unit held for another customer is not offered."""
        reservation = self.env["real.estate.reservation"].create(
            {"partner_id": self.customer_b.partner_id.id, "unit_id": self.unit_free.id}
        )
        reservation.with_user(self.agent).action_agent_confirm()
        codes = {u["code"] for u in self._call("units", self.key_a).json()["data"]}
        self.assertNotIn("HNC-API-0201", codes)
        self._error(
            self._call(f"units/{self.unit_free.id}", self.key_a), 404, "not_found"
        )
        # Customer B still sees the unit they hold.
        response = self._call(f"units/{self.unit_free.id}", self.key_b)
        self.assertEqual(response.json()["state"], "on_hold")

    # AC-15.2

    def test_ac_15_2_authentication(self):
        """BR-55: no key or a wrong key is 401; a staff key is 403."""
        self._error(self._call("units"), 401, "unauthorized")
        self._error(self._call("units", "not-a-key"), 401, "unauthorized")
        response = self._call("contracts", self.key_agent)
        self._error(response, 403, "forbidden")
        self.assertNotIn("HNC", response.text)

    # AC-15.3

    def test_ac_15_3_request_a_reservation(self):
        """BR-57: the request is the customer's, goes to the project's agent
        and leaves the unit available."""
        response = self._request(
            note="Call me after 5 pm",
            nationality="egyptian",
            national_id=NATIONAL_ID,
        )
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        self.assertEqual(data["state"], "requested")
        self.assertEqual(data["unit"]["name"], "HNC-API-0201")
        self.assertEqual(data["amount"], 100_000)
        reservation = self.env["real.estate.reservation"].browse(data["id"])
        self.assertEqual(reservation.partner_id, self.customer_a.partner_id)
        self.assertEqual(reservation.user_id, self.agent)
        self.assertEqual(reservation.customer_national_id, NATIONAL_ID)
        self.assertEqual(reservation.note, "Call me after 5 pm")
        self.assertEqual(reservation.activity_ids.user_id, self.agent)
        self.assertEqual(self.unit_free.state, "available")
        # The customer's contact is not changed by the portal.
        self.assertFalse(self.customer_a.partner_id.national_id)
        # It is listed among the customer's reservations.
        mine = self._call("reservations", self.key_a).json()
        self.assertEqual([r["id"] for r in mine["data"]], [reservation.id])

    def test_ac_15_3_refused_requests(self):
        """BR-57 / BR-49: unit not available, duplicate, too many."""
        # Customer A's own contract unit: visible, but not available.
        self._error(self._request(unit_id=self.unit_a.id), 409, "unit_not_available")
        # Customer B's contract unit: not even visible to A.
        self._error(self._request(unit_id=self.unit_b.id), 404, "not_found")
        self._error(self._request(unit_id=999_999), 404, "not_found")
        self.assertEqual(self._request().status_code, 201)
        self._error(self._request(), 409, "duplicate_request")
        units = self.unit_free_2 | self.unit_free_2.copy({"code": "HNC-API-0203"})
        units |= self.unit_free_2.copy({"code": "HNC-API-0204"})
        units |= self.unit_free_2.copy({"code": "HNC-API-0205"})
        for unit in units:
            self.assertEqual(self._request(unit_id=unit.id).status_code, 201)
        extra = self.unit_free_2.copy({"code": "HNC-API-0206"})
        self._error(self._request(unit_id=extra.id), 409, "too_many_requests")

    def test_ac_15_3_validation_errors(self):
        """BR-58: a bad body is 400, bad values are 422, nothing is created."""
        Reservation = self.env["real.estate.reservation"]
        before = Reservation.search_count([])
        self._error(self._request(unit_id="x"), 400, "bad_request")
        response = self.url_open(
            "/api/v1/reservations",
            data="not json",
            headers={
                "Authorization": f"Bearer {self.key_a}",
                "Content-Type": "application/json",
            },
        )
        self._error(response, 400, "bad_request")
        self._error(
            self._request(nationality="egyptian", national_id="12345678901234"),
            422,
            "validation_error",
        )
        self._error(self._request(nationality="foreign"), 422, "validation_error")
        self._error(self._request(national_id=NATIONAL_ID), 422, "validation_error")
        self._error(self._request(note="x" * 2001), 422, "validation_error")
        self.assertEqual(Reservation.search_count([]), before)

    # AC-15.4

    def test_ac_15_4_my_contracts_and_installments(self):
        """BR-56: the customer reads their contract and its schedule."""
        data = self._call("contracts", self.key_a).json()
        self.assertEqual([c["id"] for c in data["data"]], [self.contract_a.id])
        contract = self._call(f"contracts/{self.contract_a.id}", self.key_a).json()
        self.assertEqual(contract["reference"], self.contract_a.name)
        self.assertEqual(contract["unit"]["name"], "HNC-API-0101")

        lines = self._call("installments", self.key_a, params={"limit": 100}).json()
        self.assertEqual(lines["meta"]["total"], len(self.contract_a.installment_ids))
        self.assertEqual(
            {line["contract"]["id"] for line in lines["data"]}, {self.contract_a.id}
        )
        self.assertEqual(
            sum(line["amount"] for line in lines["data"]),
            sum(self.contract_a.installment_ids.mapped("amount")),
        )

    def test_ac_15_4_customer_a_cannot_read_customer_b(self):
        """BR-56: customer B's rows are "not found" for customer A, and never
        in A's lists."""
        reservation_b = self._request(key=self.key_b).json()
        self._error(
            self._call(f"reservations/{reservation_b['id']}", self.key_a),
            404,
            "not_found",
        )
        self.assertEqual(self._call("reservations", self.key_a).json()["data"], [])
        self._error(
            self._call(f"contracts/{self.contract_b.id}", self.key_a), 404, "not_found"
        )
        self._error(
            self._call(
                "installments", self.key_a, params={"contract_id": self.contract_b.id}
            ),
            404,
            "not_found",
        )
        self._error(self._call(f"units/{self.unit_b.id}", self.key_a), 404, "not_found")
        # And customer B sees their own.
        self.assertEqual(
            self._call(f"contracts/{self.contract_b.id}", self.key_b).status_code, 200
        )

    def test_ac_15_4_portal_rights_are_read_only(self):
        """BR-56: through the ORM too, a customer reads only their rows and
        writes nothing."""
        Contract = self.env["real.estate.contract"].with_user(self.customer_a)
        self.assertEqual(Contract.search([]), self.contract_a)
        self.assertFalse(Contract.has_access("write"))
        self.assertFalse(self.contract_a.with_user(self.customer_a).has_access("write"))
        Reservation = self.env["real.estate.reservation"].with_user(self.customer_a)
        self.assertFalse(Reservation.has_access("create"))
        # Staff rules are untouched: the agent still sees both contracts.
        self.assertEqual(
            self.env["real.estate.contract"].with_user(self.agent).search([]),
            self.contract_a | self.contract_b,
        )

    # AC-15.5

    def test_ac_15_5_errors_are_json(self):
        """BR-58: unknown paths and bad parameters answer JSON errors."""
        self._error(self._call("nothing-here", self.key_a), 404, "not_found")
        self._error(
            self._call("units", self.key_a, params={"limit": 1000}), 400, "bad_request"
        )
        self._error(
            self._call("units", self.key_a, params={"page": "x"}), 400, "bad_request"
        )
        self._error(
            self._call("reservations", self.key_a, params={"state": "nope"}),
            400,
            "bad_request",
        )

    # AC-15.6

    def test_ac_15_6_openapi_lists_every_route(self):
        """The OpenAPI file is served and describes every API route."""
        response = self.url_open("/api/v1/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        self.assertEqual(spec, openapi_spec())
        routes = {
            rule.rule
            for rule in self.env["ir.http"].routing_map().iter_rules()
            if rule.rule.startswith("/api/v1/") and rule.rule != "/api/v1/openapi.json"
        }
        documented = {
            "/api/v1" + path.replace("{", "<int:").replace("}", ">")
            for path in spec["paths"]
        }
        self.assertEqual(routes, documented)
