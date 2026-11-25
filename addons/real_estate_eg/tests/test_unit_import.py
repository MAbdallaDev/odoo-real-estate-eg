import base64
import csv
import io

import openpyxl

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.misc import file_open

from .common import RealEstateCommon

HEADER = [
    "code",
    "project_code",
    "unit_type",
    "bedrooms",
    "area",
    "floor",
    "list_price",
]


@tagged("post_install", "-at_install")
class TestUnitImport(RealEstateCommon):
    """US-08 / BR-39: import units from a CSV or .xlsx file, matched by unit
    code, all or nothing, with every bad row reported. Every import runs as a
    real user (with_user), never as admin; nothing relies on demo data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_pss = cls.env["real.estate.project"].create(
            {"name": "Palm Shores Sahel", "code": "PSS", "location": "North Coast"}
        )

    # Helpers

    def _rows_200(self):
        """§6.2-style rows: 100 Horizon apartments and 100 Sahel chalets."""
        rows = []
        for building in range(1, 11):
            for floor in range(1, 6):
                for unit in range(1, 3):
                    rows.append(
                        [
                            f"HNC-B{building + 10:02d}-{floor:02d}{unit:02d}",
                            "HNC",
                            "apartment",
                            3,
                            165,
                            floor,
                            8_580_000,
                        ]
                    )
                    rows.append(
                        [
                            f"PSS-B{building:02d}-{floor:02d}{unit:02d}",
                            "PSS",
                            "Chalet",  # the label works as well as the key
                            2,
                            95,
                            floor,
                            6_460_000,
                        ]
                    )
        return rows

    def _file(self, rows, ext="csv", header=None):
        table = [header or HEADER, *rows]
        if ext == "xlsx":
            book = openpyxl.Workbook()
            for row in table:
                book.active.append(row)
            stream = io.BytesIO()
            book.save(stream)
            return stream.getvalue()
        stream = io.StringIO()
        csv.writer(stream).writerows(table)
        return stream.getvalue().encode()

    def _wizard(self, user, content, filename):
        return (
            self.env["real.estate.unit.import"]
            .with_user(user)
            .create({"file": base64.b64encode(content), "filename": filename})
        )

    def _import(self, rows, ext="csv", user=None, header=None):
        content = self._file(rows, ext, header)
        wizard = self._wizard(user or self.manager, content, f"units.{ext}")
        return wizard._import_file()

    def _import_error(self, content, filename):
        """The UserError text of a failed import. Deliberately not
        assertRaises: Odoo's assertRaises rolls back a savepoint, which would
        hide rows written before the error. Here they would stay visible."""
        wizard = self._wizard(self.manager, content, filename)
        try:
            wizard._import_file()
        except UserError as error:
            return str(error)
        self.fail("the import did not fail")

    def _units(self):
        return (
            self.env["real.estate.unit"]
            .with_context(active_test=False)
            .search([("company_id", "=", self.env.company.id)])
        )

    # ------------------------------------------------------------------
    # AC-08.1: a file of 200 units creates 200 units
    # ------------------------------------------------------------------

    def test_ac_08_1_import_200_units(self):
        """US-08 / AC-08.1: 200 rows create 200 units with the file's values,
        from a CSV file and from an .xlsx file."""
        for ext in ("csv", "xlsx"):
            with self.subTest(ext=ext):
                before = self._units()
                counts = self._import(self._rows_200(), ext)
                new = self._units() - before
                self.assertEqual(len(new), 200)
                self.assertEqual(counts, {"created": 200, "updated": 0, "unchanged": 0})
                chalet = new.filtered(lambda u: u.code == "PSS-B03-0402")
                self.assertRecordValues(
                    chalet,
                    [
                        {
                            "project_id": self.project_pss.id,
                            "unit_type": "chalet",
                            "bedrooms": 2,
                            "area": 95,
                            "floor": 4,
                            "list_price": 6_460_000,
                        }
                    ],
                )
                new.unlink()  # the .xlsx round starts from the same units

        # The dialog's button gives the counts as a notification.
        content = self._file(self._rows_200()[:3])
        action = self._wizard(self.manager, content, "units.csv").action_import()
        self.assertEqual(action["tag"], "display_notification")
        self.assertIn("3 created, 0 updated, 0 unchanged", action["params"]["message"])

    # ------------------------------------------------------------------
    # AC-08.2: importing again creates nothing; a changed price updates
    # ------------------------------------------------------------------

    def test_ac_08_2_reimport_updates(self):
        """AC-08.2 / BR-08: the same file again creates nothing; a new price
        updates that unit only; a contract on it keeps its frozen price."""
        contract = self.create_contract(unit=self.unit_3br)
        rows = self._rows_200()
        rows.append(["HNC-B07-0302", "HNC", "apartment", 3, 165, 3, 8_580_000])
        self.assertEqual(self._import(rows)["created"], 200)
        count = len(self._units())

        counts = self._import(rows)
        self.assertEqual(counts, {"created": 0, "updated": 0, "unchanged": 201})
        self.assertEqual(len(self._units()), count)

        rows[-1][-1] = 9_000_000
        counts = self._import(rows, "xlsx")
        self.assertEqual(counts, {"created": 0, "updated": 1, "unchanged": 200})
        self.assertEqual(len(self._units()), count)
        self.assertEqual(self.unit_3br.list_price, 9_000_000)
        self.assertEqual(contract.price, 8_580_000)

    def test_reimport_archived_unit(self):
        """BR-39: an archived unit with the file's code is updated and made
        active again, not duplicated."""
        self.unit_2br.active = False
        row = ["HNC-B07-0301", "HNC", "apartment", 2, 125, 3, 6_600_000]
        counts = self._import([row])
        self.assertEqual(counts, {"created": 0, "updated": 1, "unchanged": 0})
        self.assertTrue(self.unit_2br.active)
        self.assertEqual(self.unit_2br.list_price, 6_600_000)

    # ------------------------------------------------------------------
    # AC-08.3: one unknown project, nothing imported, row number + reason
    # ------------------------------------------------------------------

    def test_ac_08_3_unknown_project_nothing_imported(self):
        """AC-08.3: row 7 names project XXX: nothing is created or changed,
        and the error gives row 7 and the reason. CSV and .xlsx alike."""
        rows = self._rows_200()[:9]
        # The header is row 1, so the first unit is row 2.
        rows.insert(0, ["HNC-B07-0302", "HNC", "apartment", 3, 165, 3, 9_999_999])
        rows[5][1] = "XXX"  # spreadsheet row 7
        before = self._units()
        for ext in ("csv", "xlsx"):
            with self.subTest(ext=ext):
                message = self._import_error(self._file(rows, ext), f"units.{ext}")
                self.assertIn("Nothing was imported", message)
                self.assertIn("Row 7: unknown project XXX", message)
                self.assertNotIn("Row 6", message)
                self.assertEqual(self._units(), before)
                self.assertEqual(self.unit_3br.list_price, 8_580_000)

    def test_import_row_errors(self):
        """BR-39: every bad row is reported with its number in one error, and
        nothing is written."""
        good = ["HNC-B20-0101", "HNC", "apartment", 2, 125, 1, 6_500_000]
        rows = [
            ["HNC-B20-0102", "HNC", "villa", 2, 125, 1, 6_500_000],  # row 2
            ["HNC-B20-0103", "HNC", "apartment", 2, 0, 1, 6_500_000],  # row 3
            ["HNC-B20-0104", "HNC", "apartment", 2, 125, 1, -1],  # row 4
            good,  # row 5
            list(good),  # row 6: same code as row 5
            ["HNC-B20-0105", "HNC", "duplex", 2.5, 240, 1, 12_480_000],  # row 7
            ["HNC-B20-0106", "HNC", "duplex", 3, 240, 1, "12,480,000"],  # row 8
            ["", "", "", "", "", "", ""],  # row 9: empty, skipped, still counted
            ["", "HNC", "duplex", 3, 240, 1, "abc"],  # row 10
        ]
        before = self._units()
        message = self._import_error(self._file(rows), "units.csv")
        for expected in (
            "Row 2: unit_type villa is not one of",
            "Row 3: area must be > 0",
            "Row 4: list_price must be >= 0",
            "Row 6: code HNC-B20-0101 is already on row 5",
            "Row 7: bedrooms 2.5 must be a whole number",
            "Row 8: list_price 12,480,000: write numbers without commas",
            "Row 10: code is empty; list_price abc is not a number",
        ):
            self.assertIn(expected, message)
        self.assertNotIn("Row 5", message)
        self.assertNotIn("Row 9", message)
        self.assertEqual(self._units(), before)

    def test_import_bad_files(self):
        """BR-39: a file-level problem is one clear error, and nothing is written."""
        before = self._units()
        header = [column for column in HEADER if column != "area"] + ["colour"]
        cases = [
            (self._file([["X"]], header=header), "units.csv", "missing columns: area"),
            (
                self._file([["X"]], header=header),
                "units.csv",
                "unknown columns: colour",
            ),
            (b"code;project_code\nA;HNC\n", "units.csv", "not semicolons"),
            (self._file([]), "units.csv", "no units after the header"),
            ("code\n\xe9".encode("latin-1"), "units.csv", "not UTF-8"),
            (b"not a zip", "units.xlsx", "not a valid .xlsx"),
            (b"anything", "units.xls", "save it as .xlsx"),
            (b"anything", "units.txt", "Upload a .csv or .xlsx file"),
        ]
        for content, filename, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, self._import_error(content, filename))
        self.assertEqual(self._units(), before)

    def test_sample_file_imports(self):
        """US-08: the sample file offered in the dialog imports cleanly."""
        self.env["real.estate.project"].create(
            {"name": "Capital Business Park", "code": "CBP"}
        )
        path = "real_estate_eg/static/sample/real_estate_units_sample.csv"
        with file_open(path, "rb") as sample:
            content = sample.read()
        wizard = self._wizard(self.manager, content, "real_estate_units_sample.csv")
        counts = wizard._import_file()
        # HNC-B07-0301 / 0302 already exist (common.py) with the same values.
        self.assertEqual(counts, {"created": 6, "updated": 0, "unchanged": 2})

    # ------------------------------------------------------------------
    # Rights and companies
    # ------------------------------------------------------------------

    def test_import_rights(self):
        """BR-35: only the manager imports units; BR-01: codes are matched in
        the user's company only."""
        content = self._file(self._rows_200()[:1])
        for user in (self.agent_a, self.collections, self.accountant):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._wizard(user, content, "units.csv")

        company_2 = self.setup_other_company(name="Nile Heights West")["company"]
        env_2 = self.env(
            context=dict(self.env.context, allowed_company_ids=[company_2.id])
        )
        project_2 = env_2["real.estate.project"].create(
            {"name": "West Towers", "code": "WTW", "company_id": company_2.id}
        )
        unit_2 = env_2["real.estate.unit"].create(
            {
                "code": "WTW-A01-0101",
                "project_id": project_2.id,
                "unit_type": "apartment",
                "area": 120,
                "list_price": 5_000_000,
            }
        )
        # Company 2's project is unknown to a company 1 import.
        with self.assertRaises(UserError) as error:
            self._import([["WTW-A01-0102", "WTW", "apartment", 2, 120, 1, 1]])
        self.assertIn("Row 2: unknown project WTW", str(error.exception))
        # The same code in company 1 is a different unit: created, not matched.
        counts = self._import([["WTW-A01-0101", "HNC", "apartment", 2, 120, 1, 1]])
        self.assertEqual(counts["created"], 1)
        self.assertEqual(unit_2.list_price, 5_000_000)
        self.assertEqual(unit_2.project_id, project_2)
