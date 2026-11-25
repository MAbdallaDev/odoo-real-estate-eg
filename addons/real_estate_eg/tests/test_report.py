import re

from lxml import html as lxml_html

from odoo.tests import tagged

from ..report.real_estate_contract_report import ARABIC_LABELS, SELECTION_FIELDS
from .common import RealEstateCommon

REPORT = "real_estate_eg.action_report_contract"
ARABIC = re.compile("[؀-ۿ]")


def _text(nodes):
    """All text under `nodes`, spaces (no-break included) squeezed to one."""
    text = " ".join(node.text_content() for node in nodes)
    return " ".join(text.replace("\xa0", " ").split())


@tagged("post_install", "-at_install")
class TestContractReport(RealEstateCommon):
    """US-07 / BR-38: the bilingual contract report. In a test run Odoo
    renders reports as HTML (not PDF), which is what these tests read."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.currency_id = cls.env.ref("base.EGP").sudo()
        cls.env.ref("base.EGP").sudo().active = True

    def render(self, contract, user=None):
        """The report as the given user (default: agent A) prints it, parsed."""
        user = user or self.agent_a
        content, report_type = (
            self.env["ir.actions.report"]
            .with_user(user)
            ._render_qweb_html(REPORT, contract.ids)
        )
        self.assertEqual(report_type, "html")
        return lxml_html.fromstring(content)

    def sides(self, tree):
        """(English text, Arabic text): the English cells, and everything
        inside an element marked right-to-left."""
        english = _text(tree.xpath("//td[contains(@class, 'o_re_en')]"))
        arabic = _text(tree.xpath("//*[@dir='rtl']"))
        return english, arabic

    def example_a(self):
        """§6.6 Example A: 8,580,000 on 10 Jan 2027, NH-STD-8Q (34 lines)."""
        contract = self.create_contract()
        contract.with_user(self.agent_a).date = "2027-01-10"
        self.generate_schedule(contract, self.plan_std)
        return contract

    def test_ac_07_1_bilingual_side_by_side(self):
        contract = self.example_a()
        tree = self.render(contract)
        english, arabic = self.sides(tree)
        # Parties, unit, price and plan: English labels on the left...
        for word in [
            "Preliminary Sale Contract",
            "Seller:",
            self.env.company.name,
            "Buyer:",
            "Fictional Buyer EG",
            "National ID: 29901158800017",
            "Sales agent:",
            self.agent_a.name,
            "Unit code: HNC-B07-0302",
            "Project: Horizon New Cairo",
            "Type: Apartment",
            "Area: 165 m²",
            "Contract price: 8,580,000 EGP",
            "Payment plan: Standard 8 years (NH-STD-8Q)",
            "Down payment: 10%",
            "Installments: 32, Quarterly",
            "Maintenance deposit: 8%, at delivery",
        ]:
            self.assertIn(word, english)
        # ...and the same in Arabic, inside dir="rtl".
        for word in [
            "عقد بيع ابتدائي",
            "البائع:",
            "المشتري:",
            "Fictional Buyer EG",
            "الرقم القومي: 29901158800017",
            "مندوب المبيعات:",
            "كود الوحدة: HNC-B07-0302",
            "المشروع: Horizon New Cairo",
            "النوع: شقة",
            "سعر العقد: 8,580,000 EGP",
            "نظام السداد: Standard 8 years (NH-STD-8Q)",
            "عدد الأقساط: 32، ربع سنوي",
            "وديعة الصيانة: 8%، عند الاستلام",
        ]:
            self.assertIn(word, arabic)
        # No Arabic on the English side, and every Arabic letter of the
        # page sits inside a right-to-left element.
        self.assertFalse(ARABIC.search(english))
        all_arabic = ARABIC.findall(_text([tree.body]))
        self.assertEqual(len(all_arabic), len(ARABIC.findall(arabic)))

    def test_arabic_label_for_every_value(self):
        """BR-38: a selection value without an Arabic word would print
        nothing on the Arabic side; caught here, not on paper."""
        for key, (model, field) in SELECTION_FIELDS.items():
            values = {
                value for value, _label in self.env[model]._fields[field].selection
            }
            self.assertEqual(values, set(ARABIC_LABELS[key]), key)

    def test_ac_07_2_long_customer_name(self):
        name = "Fictional Buyer Abdelrahman Mohamed Abdelaziz El-Sayed Hasan"
        self.assertEqual(len(name), 60)
        self.customer_eg.name = name
        tree = self.render(self.create_contract())
        # In full, on both sides: never cut.
        buyers = tree.xpath("//span[contains(@class, 'o_re_buyer')]")
        self.assertEqual([b.text_content() for b in buyers], [name, name])

    def test_ac_07_3_amount_format(self):
        tree = self.render(self.example_a())
        amounts = [
            " ".join(span.text_content().replace("\xa0", " ").split())
            for span in tree.xpath("//span[contains(@class, 'o_re_amount')]")
        ]
        self.assertIn("8,580,000 EGP", amounts)
        for amount in amounts:
            # Whole pounds, thousands separators, the code: never "LE" or ".00".
            self.assertRegex(amount, r"^\d{1,3}(,\d{3})* EGP$")
        # Inside Arabic text the amount stays left-to-right.
        for span in tree.xpath(
            "//*[@dir='rtl']//span[contains(@class, 'o_re_amount')]"
        ):
            self.assertEqual(span.get("dir"), "ltr")
