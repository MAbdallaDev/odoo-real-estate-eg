import html
import json
import re

from odoo.tests import HttpCase, new_test_user, tagged

AGENT = "real_estate_eg.group_real_estate_agent"
# BR-06: a valid Egyptian national ID (born 15 January 1999).
NATIONAL_ID = "29901158800017"
# The token Odoo writes into every page it renders (web.layout).
CSRF_IN_PAGE = re.compile(r'csrf_token: "([^"]+)"')


@tagged("post_install", "-at_install")
class TestPortalPages(HttpCase):
    """US-16 (v1.1): the customer pages in Odoo's portal, and the API called
    with the browser session. BR-59, BR-60.

    Customers A and B are portal users (password = login). A has a contract
    on unit 0101 and a request on unit 0201; B has a contract on unit 0102.
    Unit 0202 is available. The agent is staff."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = new_test_user(cls.env, login="re_web_agent", groups=AGENT)
        cls.customer_a = new_test_user(
            cls.env, login="re_web_customer_a", groups="base.group_portal"
        )
        cls.customer_b = new_test_user(
            cls.env, login="re_web_customer_b", groups="base.group_portal"
        )
        cls.project = cls.env["real.estate.project"].create(
            {
                "name": "Horizon Web Heights",
                "code": "HWH",
                "user_id": cls.agent.id,
                "reservation_amount": 100_000,
            }
        )
        cls.unit_a, cls.unit_b, cls.unit_requested, cls.unit_free = cls.env[
            "real.estate.unit"
        ].create(
            [
                {
                    "code": code,
                    "project_id": cls.project.id,
                    "unit_type": "apartment",
                    "bedrooms": 2,
                    "area": 125,
                    "list_price": 6_500_000,
                }
                for code in ("HWH-0101", "HWH-0102", "HWH-0201", "HWH-0202")
            ]
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
        cls.contract_b = Contract.create(
            {
                "partner_id": cls.customer_b.partner_id.id,
                "unit_id": cls.unit_b.id,
                "user_id": cls.agent.id,
                "date": "2026-01-10",
            }
        )
        cls.request_a = cls.env["real.estate.reservation"].create(
            {
                "partner_id": cls.customer_a.partner_id.id,
                "unit_id": cls.unit_requested.id,
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _open(self, url, **kwargs):
        # The request runs on the test cursor: write what the test set up
        # first, and read fresh values after.
        self.env.flush_all()
        response = self.url_open(url, **kwargs)
        self.env.invalidate_all()
        return response

    def _csrf_token(self):
        """The CSRF token of the current session, as a page gives it to the
        OWL components (odoo.csrf_token)."""
        response = self._open("/my")
        self.assertEqual(response.status_code, 200, response.text)
        return CSRF_IN_PAGE.search(response.text).group(1)

    def _post_request(self, headers=None):
        return self._open(
            "/api/v1/reservations",
            method="POST",
            json={
                "unit_id": self.unit_free.id,
                "nationality": "egyptian",
                "national_id": NATIONAL_ID,
            },
            headers=headers,
        )

    def _error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertTrue(response.headers["Content-Type"].startswith("application/json"))
        self.assertEqual(response.json()["error"]["code"], code)

    def _requests_on_free_unit(self):
        return self.env["real.estate.reservation"].search_count(
            [("unit_id", "=", self.unit_free.id)]
        )

    # ------------------------------------------------------------------
    # BR-59: the API with the browser session
    # ------------------------------------------------------------------

    def test_us_16_session_reads_the_api(self):
        """A logged-in customer's page reads the API without a key, and still
        sees only their own records (BR-56)."""
        self._login(self.customer_a)
        response = self._open("/api/v1/contracts")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [contract["id"] for contract in response.json()["data"]],
            [self.contract_a.id],
        )
        response = self._open("/api/v1/units")
        self.assertEqual(response.status_code, 200, response.text)
        codes = {unit["code"] for unit in response.json()["data"]}
        self.assertIn("HWH-0202", codes)
        self.assertNotIn("HWH-0102", codes)
        self._error(
            self._open(f"/api/v1/contracts/{self.contract_b.id}"), 404, "not_found"
        )

    def test_ac_16_1_session_post_needs_the_csrf_header(self):
        """A POST with the session alone, or with a wrong token, is refused
        (403 JSON) and creates nothing; with the page's token it passes."""
        self._login(self.customer_a)
        self._error(self._post_request(), 403, "csrf_failed")
        self._error(
            self._post_request({"X-CSRF-Token": "0123456789abcdefo9999999999"}),
            403,
            "csrf_failed",
        )
        # A token in the form field Odoo uses elsewhere is not enough either.
        self._error(
            self._open(
                "/api/v1/reservations",
                method="POST",
                data={"csrf_token": self._csrf_token()},
            ),
            403,
            "csrf_failed",
        )
        self.assertEqual(self._requests_on_free_unit(), 0)

        response = self._post_request({"X-CSRF-Token": self._csrf_token()})
        self.assertEqual(response.status_code, 201, response.text)
        reservation = self.env["real.estate.reservation"].browse(response.json()["id"])
        self.assertEqual(reservation.partner_id, self.customer_a.partner_id)
        self.assertEqual(reservation.state, "requested")
        self.assertEqual(reservation.unit_id, self.unit_free)

    def test_ac_16_1_token_of_another_session_is_refused(self):
        """The token is bound to the session: customer B's token does not
        work in customer A's session."""
        self._login(self.customer_b)
        token_b = self._csrf_token()
        self._login(self.customer_a)
        self._error(self._post_request({"X-CSRF-Token": token_b}), 403, "csrf_failed")
        self.assertEqual(self._requests_on_free_unit(), 0)

    def test_ac_16_1_anonymous_and_staff_sessions(self):
        """No session and no key is 401; a staff session is 403 (BR-55), for
        reads and for a POST with a valid token."""
        self._error(self._open("/api/v1/units"), 401, "unauthorized")
        self._error(self._post_request(), 401, "unauthorized")

        self._login(self.agent)
        response = self._open("/api/v1/contracts")
        self._error(response, 403, "forbidden")
        self.assertNotIn("HWH", response.text)
        self._error(
            self._post_request({"X-CSRF-Token": self._csrf_token()}), 403, "forbidden"
        )
        self.assertEqual(self._requests_on_free_unit(), 0)

    # ------------------------------------------------------------------
    # BR-60: the pages
    # ------------------------------------------------------------------

    def test_ac_16_2_pages_mount_their_component(self):
        """Each page is served to the customer with its OWL component; the
        unit page gets the projects and unit types for its filters."""
        self._login(self.customer_a)
        pages = {
            "/my/real-estate/units": "real_estate_eg_portal.UnitList",
            "/my/real-estate/reservations": "real_estate_eg_portal.ReservationList",
            "/my/real-estate/contracts": "real_estate_eg_portal.ContractList",
            f"/my/real-estate/contracts/{self.contract_a.id}": (
                "real_estate_eg_portal.ContractDetail"
            ),
        }
        for url, component in pages.items():
            with self.subTest(url=url):
                response = self._open(url)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(f'<owl-component name="{component}"', response.text)
        response = self._open("/my/real-estate/units")
        props = json.loads(
            html.unescape(
                re.search(r'<owl-component [^>]*props="([^"]*)"', response.text).group(
                    1
                )
            )
        )
        self.assertIn(
            {"id": self.project.id, "name": "Horizon Web Heights"}, props["projects"]
        )
        self.assertIn({"value": "apartment", "label": "Apartment"}, props["unitTypes"])
        response = self._open(f"/my/real-estate/contracts/{self.contract_a.id}")
        self.assertIn(self.contract_a.name, response.text)

    def test_ac_16_2_assets_are_in_the_frontend_bundle(self):
        """The components, their templates and styles are served in the
        frontend bundles the pages load (the browser itself is not run in
        CI, see the design note)."""
        self._login(self.customer_a)
        page = self._open("/my/real-estate/units").text
        scripts = re.findall(r'src="(/web/assets/[^"]*\.js)"', page)
        styles = re.findall(r'href="(/web/assets/[^"]*\.css)"', page)
        self.assertTrue(scripts and styles, "no asset bundle on the page")
        js = "".join(self._open(url).text for url in scripts)
        for name in (
            "real_estate_eg_portal.api",
            "real_estate_eg_portal.UnitList",
            "real_estate_eg_portal.ReserveForm",
            "real_estate_eg_portal.ContractDetail",
            "X-CSRF-Token",
        ):
            with self.subTest(name=name):
                self.assertIn(name, js)
        css = "".join(self._open(url).text for url in styles)
        self.assertIn("o_re_unit_card", css)

    def test_ac_16_2_who_may_open_the_pages(self):
        """Anonymous visitors go to the login page; staff go back to /my;
        another customer's contract is not found."""
        response = self._open("/my/real-estate/units", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/web/login", response.headers["Location"])

        self._login(self.customer_a)
        response = self._open(f"/my/real-estate/contracts/{self.contract_b.id}")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.contract_b.name, response.text)

        self._login(self.agent)
        for url in ("/my/real-estate/units", "/my/real-estate/contracts"):
            with self.subTest(url=url):
                response = self._open(url, allow_redirects=False)
                self.assertIn(response.status_code, (302, 303))
                self.assertTrue(response.headers["Location"].endswith("/my"))

    def test_ac_16_3_home_cards_and_counters(self):
        """The portal home shows the cards to a customer, with the number of
        their own reservations and contracts; staff get no card."""
        self._login(self.customer_a)
        response = self._open("/my")
        self.assertIn("/my/real-estate/units", response.text)
        self.assertIn("re_reservation_count", response.text)
        counters = self.make_jsonrpc_request(
            "/my/counters", {"counters": ["re_reservation_count", "re_contract_count"]}
        )
        self.assertEqual(counters["re_reservation_count"], 1)
        self.assertEqual(counters["re_contract_count"], 1)

        self._login(self.customer_b)
        counters = self.make_jsonrpc_request(
            "/my/counters", {"counters": ["re_reservation_count", "re_contract_count"]}
        )
        self.assertEqual(counters["re_reservation_count"], 0)
        self.assertEqual(counters["re_contract_count"], 1)

        self._login(self.agent)
        response = self._open("/my")
        self.assertNotIn("/my/real-estate/units", response.text)
        counters = self.make_jsonrpc_request(
            "/my/counters", {"counters": ["re_reservation_count", "re_contract_count"]}
        )
        self.assertEqual(counters["re_reservation_count"], 0)
        self.assertEqual(counters["re_contract_count"], 0)
