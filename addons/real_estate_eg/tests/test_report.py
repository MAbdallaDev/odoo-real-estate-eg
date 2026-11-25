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


def _cell(row, css_class):
    """The text of the cell of `row` with this class."""
    return _text(row.xpath(f"td[contains(@class, '{css_class}')]"))


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
        # Every schedule line, one row each, described in both languages.
        rows = tree.xpath("//tr[contains(@class, 'o_re_line')]")
        self.assertEqual(len(contract.installment_ids), 34)
        self.assertEqual(len(rows), 34)
        expected = [("Down Payment", "المقدم", "10/01/2027", "858,000 EGP")]
        expected += [
            (f"Installment {k}", f"القسط {k}", None, "241,313 EGP")
            for k in range(1, 32)
        ]
        expected += [
            ("Installment 32", "القسط 32", "10/01/2035", "241,297 EGP"),
            ("Maintenance Deposit", "وديعة الصيانة", "On delivery", "686,400 EGP"),
        ]
        for row, (en_name, ar_name, due, amount) in zip(rows, expected, strict=True):
            self.assertEqual(_cell(row, "o_re_line_en"), en_name)
            self.assertEqual(_cell(row, "o_re_line_ar"), ar_name)
            self.assertEqual(
                row.xpath("td[contains(@class, 'o_re_line_ar')]/@dir"), ["rtl"]
            )
            if due:
                self.assertIn(due, _cell(row, "o_re_date"))
            self.assertEqual(_cell(row, "o_re_money"), amount)
        self.assertIn("عند الاستلام", arabic)  # the deposit's date, in Arabic
        total = tree.xpath("//tr[contains(@class, 'o_re_total')]")[0]
        self.assertEqual(_cell(total, "o_re_money"), "8,580,000 EGP")
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

    def test_print_draft_and_read_only_roles(self):
        """A draft is marked as not for signature; with no schedule yet the
        table is replaced by one line. Read-only roles can print too."""
        draft = self.create_contract()
        english, arabic = self.sides(self.render(draft))
        self.assertIn("DRAFT: not for signature", english)
        self.assertIn("مسودة: غير صالحة للتوقيع", arabic)
        self.assertIn("No schedule generated yet.", english)
        self.assertIn("لم يتم إنشاء جدول السداد بعد.", arabic)

        confirmed = self.add_schedule(self.create_contract(unit=self.unit_2br))
        confirmed.with_user(self.manager).action_confirm()
        for user in (self.collections, self.accountant):
            tree = self.render(confirmed, user=user)
            english, _arabic = self.sides(tree)
            self.assertNotIn("DRAFT", english)
            self.assertEqual(
                len(tree.xpath("//tr[contains(@class, 'o_re_line')]")),
                len(confirmed.installment_ids),
            )
