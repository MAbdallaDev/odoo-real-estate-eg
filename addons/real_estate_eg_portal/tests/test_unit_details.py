import base64
import io

from PIL import Image

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

AGENT = "real_estate_eg.group_real_estate_agent"
MANAGER = "real_estate_eg.group_real_estate_manager"
PRICE = 6_525_000


def _png(color, size=(64, 48)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


@tagged("post_install", "-at_install")
class TestUnitDetails(HttpCase):
    """US-17 (v1.1): photos, floor plan, project and payment plans on the
    portal. BR-61, BR-62, BR-63.

    Project Horizon Photo Heights offers two plans (Standard 8 years, Fast 5
    years) and has a cover photo; a third plan exists but is not offered.
    Unit 0101 has two photos and a floor plan; unit 0102 has none (it shows
    the project's photo); unit 0103 has a photo and is held for customer B.
    Project Desert Edge has an available unit and no photo or plan."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = new_test_user(cls.env, login="re_img_agent", groups=AGENT)
        cls.manager = new_test_user(cls.env, login="re_img_manager", groups=MANAGER)
        cls.customer_a = new_test_user(
            cls.env, login="re_img_customer_a", groups="base.group_portal"
        )
        cls.customer_b = new_test_user(
            cls.env, login="re_img_customer_b", groups="base.group_portal"
        )
        cls.key_a = cls._api_key(cls.customer_a)
        cls.key_b = cls._api_key(cls.customer_b)

        Plan = cls.env["real.estate.plan.template"]
        cls.plan_standard, cls.plan_fast, cls.plan_hidden = Plan.create(
            [
                {
                    "name": "Standard 8 years",
                    "code": "IMG-STD-8Q",
                    "down_payment_percent": 10,
                    "installment_count": 32,
                    "frequency": "quarterly",
                    "first_installment_months": 3,
                    "maintenance_percent": 8,
                    "maintenance_due": "delivery",
                },
                {
                    "name": "Fast 5 years",
                    "code": "IMG-FST-5M",
                    "down_payment_percent": 20,
                    "installment_count": 60,
                    "frequency": "monthly",
                    "first_installment_months": 1,
                    "maintenance_percent": 8,
                    "maintenance_due": "signing",
                },
                {
                    "name": "Not offered",
                    "code": "IMG-HIDDEN",
                    "down_payment_percent": 50,
                    "installment_count": 4,
                    "frequency": "annual",
                    "first_installment_months": 12,
                    "maintenance_percent": 0,
                    "maintenance_due": "delivery",
                },
            ]
        )
        Project = cls.env["real.estate.project"]
        cls.project = Project.create(
            {
                "name": "Horizon Photo Heights",
                "code": "HPH",
                "location": "New Capital, R7",
                "expected_delivery_date": "2029-12-31",
                "user_id": cls.agent.id,
                "reservation_amount": 100_000,
                "portal_description": "<p>18 buildings around a central park.</p>",
                "plan_template_ids": [(6, 0, (cls.plan_standard | cls.plan_fast).ids)],
            }
        )
        cls.project_bare = Project.create(
            {"name": "Desert Edge", "code": "DEE", "user_id": cls.agent.id}
        )
        Unit = cls.env["real.estate.unit"]
        cls.unit_photo, cls.unit_plain, cls.unit_held, cls.unit_twin = Unit.create(
            [
                {
                    "code": code,
                    "project_id": cls.project.id,
                    "unit_type": "apartment",
                    "bedrooms": 3,
                    "area": 145,
                    "list_price": PRICE,
                }
                for code in ("HPH-0101", "HPH-0102", "HPH-0103", "HPH-0104")
            ]
        )
        cls.unit_bare = Unit.create(
            {
                "code": "DEE-0001",
                "project_id": cls.project_bare.id,
                "unit_type": "chalet",
                "bedrooms": 2,
                "area": 95,
                "list_price": 3_000_000,
            }
        )
        cls.unit_photo.floor_plan = _png("white", (90, 60))
        Photo = cls.env["real.estate.image"]
        cls.project_cover = Photo.create(
            {"project_id": cls.project.id, "image_1920": _png("blue"), "name": "Park"}
        )
        cls.photo_second, cls.photo_first = Photo.create(
            [
                {
                    "unit_id": cls.unit_photo.id,
                    "image_1920": _png("red"),
                    "name": "Bedroom",
                    "sequence": 20,
                },
                {
                    "unit_id": cls.unit_photo.id,
                    "image_1920": _png("green"),
                    "name": "Living room",
                    "sequence": 5,
                },
            ]
        )
        cls.photo_held = Photo.create(
            {"unit_id": cls.unit_held.id, "image_1920": _png("black")}
        )
        held = cls.env["real.estate.reservation"].create(
            {"partner_id": cls.customer_b.partner_id.id, "unit_id": cls.unit_held.id}
        )
        held.with_user(cls.agent).action_agent_confirm()

    @classmethod
    def _api_key(cls, user):
        return (
            cls.env["res.users.apikeys"]
            .with_user(user)
            .sudo()
            ._generate(None, "test", None)
        )

    def _call(self, path, key, params=None):
        self.env.flush_all()
        response = self.url_open(
            "/api/v1/" + path,
            params=params,
            headers={"Authorization": f"Bearer {key}"},
        )
        self.env.invalidate_all()
        return response

    def _error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()["error"]["code"], code)

    def _image(self, response):
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        return response.content

    # ------------------------------------------------------------------
    # BR-63: the unit's details
    # ------------------------------------------------------------------

    def test_us_17_unit_details(self):
        """A customer reads a unit with its photos in order, its floor plan
        and its project."""
        data = self._call(f"units/{self.unit_photo.id}", self.key_a).json()
        self.assertEqual(data["code"], "HPH-0101")
        self.assertEqual(
            [image["id"] for image in data["images"]],
            [self.photo_first.id, self.photo_second.id],
        )
        self.assertEqual(data["images"][0]["caption"], "Living room")
        self.assertEqual(
            data["images"][0]["url"], f"/api/v1/images/{self.photo_first.id}?size=1024"
        )
        self.assertEqual(data["image_url"], data["images"][0]["url"])
        self.assertEqual(
            data["floor_plan_url"], f"/api/v1/units/{self.unit_photo.id}/floor-plan"
        )
        project = data["project"]
        self.assertEqual(project["name"], "Horizon Photo Heights")
        self.assertEqual(project["location"], "New Capital, R7")
        self.assertEqual(project["expected_delivery_date"], "2029-12-31")
        self.assertEqual(project["reservation_amount"], 100_000)
        self.assertIn("central park", project["description"])
        self.assertEqual(
            project["image_url"], f"/api/v1/images/{self.project_cover.id}?size=1024"
        )

    def test_ac_17_unit_without_photos_shows_the_project_photos(self):
        """BR-61: no photo of its own → the project's; no floor plan → none."""
        data = self._call(f"units/{self.unit_plain.id}", self.key_a).json()
        self.assertEqual(
            [image["id"] for image in data["images"]], [self.project_cover.id]
        )
        self.assertIsNone(data["floor_plan_url"])
        units = {
            unit["code"]: unit
            for unit in self._call("units", self.key_a, {"limit": 100}).json()["data"]
        }
        self.assertEqual(units["HPH-0102"]["image_url"], data["images"][0]["url"])
        self.assertIsNone(units["DEE-0001"]["image_url"])

    # ------------------------------------------------------------------
    # BR-62: the plans offered, worked out on the price
    # ------------------------------------------------------------------

    def test_ac_17_plans_offered_on_the_unit_price(self):
        """Only the project's plans, with the generator's numbers (BR-15 to
        BR-18): the down payment rounded, the last installment taking the
        rounding, the maintenance deposit on top."""
        plans = {
            plan["name"]: plan
            for plan in self._call(f"units/{self.unit_photo.id}", self.key_a).json()[
                "plans"
            ]
        }
        self.assertEqual(set(plans), {"Standard 8 years", "Fast 5 years"})
        standard = plans["Standard 8 years"]
        self.assertEqual(standard["down_payment"], 652_500)
        self.assertEqual(standard["installment_count"], 32)
        self.assertEqual(standard["frequency"], "quarterly")
        # (6,525,000 - 652,500) / 32 = 183,515.625 → 183,516; the last one
        # takes the rest: 5,872,500 - 31 × 183,516 = 183,504.
        self.assertEqual(standard["installment_amount"], 183_516)
        self.assertEqual(standard["last_installment_amount"], 183_504)
        self.assertEqual(standard["first_installment_months"], 3)
        self.assertEqual(standard["maintenance"], 522_000)
        self.assertEqual(standard["maintenance_due"], "delivery")
        self.assertEqual(standard["total"], PRICE + 522_000)
        fast = plans["Fast 5 years"]
        self.assertEqual(fast["down_payment"], 1_305_000)
        self.assertEqual(fast["installment_amount"], 87_000)
        self.assertEqual(fast["last_installment_amount"], 87_000)
        self.assertEqual(fast["maintenance_due"], "signing")

        # The same numbers as a real contract's schedule at the same price.
        contract = self.env["real.estate.contract"].create(
            {
                "partner_id": self.customer_a.partner_id.id,
                "unit_id": self.unit_twin.id,
                "user_id": self.agent.id,
                "date": "2026-01-10",
            }
        )
        contract._generate_schedule(self.plan_standard)
        lines = contract.installment_ids
        down_payment = lines.filtered(lambda line: line.line_type == "down_payment")
        self.assertEqual(down_payment.amount, standard["down_payment"])
        installments = lines.filtered(lambda line: line.line_type == "installment")
        self.assertEqual(installments[:1].amount, standard["installment_amount"])
        self.assertEqual(installments[-1:].amount, standard["last_installment_amount"])
        self.assertEqual(sum(lines.mapped("amount")), standard["total"])

    # ------------------------------------------------------------------
    # BR-61: photos and floor plans follow the unit rule
    # ------------------------------------------------------------------

    def test_ac_17_images_follow_the_unit_rule(self):
        """A photo or floor plan is served only if the customer may see the
        unit (or it is the project's); otherwise it is not found."""
        self._image(self._call(f"images/{self.project_cover.id}", self.key_a))
        small = self._image(
            self._call(f"images/{self.photo_first.id}", self.key_a, {"size": "128"})
        )
        self.assertTrue(small)
        self._error(
            self._call(f"images/{self.photo_first.id}", self.key_a, {"size": "77"}),
            400,
            "bad_request",
        )
        self._image(self._call(f"units/{self.unit_photo.id}/floor-plan", self.key_a))
        self._error(
            self._call(f"units/{self.unit_plain.id}/floor-plan", self.key_a),
            404,
            "not_found",
        )
        # Unit 0103 is held for customer B: A gets nothing about it.
        self._error(
            self._call(f"images/{self.photo_held.id}", self.key_a), 404, "not_found"
        )
        self._error(
            self._call(f"units/{self.unit_held.id}/floor-plan", self.key_a),
            404,
            "not_found",
        )
        self._image(self._call(f"images/{self.photo_held.id}", self.key_b))

    def test_ac_17_projects_with_available_units(self):
        """BR-61: the banners: projects with an available unit, their cover
        and how many units are available."""
        projects = {
            project["name"]: project
            for project in self._call("projects", self.key_a, {"limit": 100}).json()[
                "data"
            ]
        }
        mine = projects["Horizon Photo Heights"]
        # 0101, 0102 and 0104 (0103 is on hold).
        self.assertEqual(mine["available_units"], 3)
        self.assertEqual(
            mine["image_url"], f"/api/v1/images/{self.project_cover.id}?size=1024"
        )
        self.assertIsNone(projects["Desert Edge"]["image_url"])
        self.assertEqual(projects["Desert Edge"]["available_units"], 1)

    # ------------------------------------------------------------------
    # BR-63: the page
    # ------------------------------------------------------------------

    def test_ac_17_unit_page(self):
        """The unit page mounts its component for a customer; a unit held
        for someone else is not found; staff go back to /my."""
        self.authenticate(self.customer_a.login, self.customer_a.login)
        response = self.url_open(f"/my/real-estate/units/{self.unit_photo.id}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(
            '<owl-component name="real_estate_eg_portal.UnitDetail"', response.text
        )
        self.assertIn("HPH-0101", response.text)
        response = self.url_open(f"/my/real-estate/units/{self.unit_held.id}")
        self.assertEqual(response.status_code, 404)

        self.authenticate(self.agent.login, self.agent.login)
        response = self.url_open(
            f"/my/real-estate/units/{self.unit_photo.id}", allow_redirects=False
        )
        self.assertIn(response.status_code, (302, 303))

    # ------------------------------------------------------------------
    # Who may change the photos
    # ------------------------------------------------------------------

    def test_ac_17_rights_on_photos(self):
        """Customers and agents only read photos; managers add them. A photo
        belongs to one project or one unit."""
        Photo = self.env["real.estate.image"]
        values = {"unit_id": self.unit_plain.id, "image_1920": _png("gray")}
        for user in (self.customer_a, self.agent):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                Photo.with_user(user).create(values)
        photo = Photo.with_user(self.manager).create(values)
        self.assertEqual(photo.company_id, self.unit_plain.company_id)
        with self.assertRaises(ValidationError):
            Photo.create({**values, "project_id": self.project.id})
        with self.assertRaises(ValidationError):
            Photo.create({"image_1920": _png("gray")})
