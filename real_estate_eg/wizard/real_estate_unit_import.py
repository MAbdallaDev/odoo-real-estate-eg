import base64
import csv
import io
import zipfile

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

# BR-39: the columns of the import file, in the order of the sample file.
REQUIRED_COLUMNS = ("code", "project_code", "unit_type", "area", "list_price")
OPTIONAL_COLUMNS = ("bedrooms", "floor")
COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
# Fields compared before writing, so an unchanged unit is not written at all.
FLOAT_FIELDS = ("area", "list_price")
PLAIN_FIELDS = ("unit_type", "bedrooms", "floor")


class RealEstateUnitImport(models.TransientModel):
    """US-08 / BR-39: import units from a CSV or Excel (.xlsx) file.

    Phase 1 reads and checks every row and writes nothing. Phase 2 runs only
    when no row is wrong: units are matched by code in the current company
    (BR-01), known units are updated, new ones created. So a file is imported
    all or nothing, and importing it again creates no duplicates."""

    _name = "real.estate.unit.import"
    _description = "Import Units"

    file = fields.Binary(required=True)
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        counts = self._import_file()
        message = self.env._(
            "%(created)s created, %(updated)s updated, %(unchanged)s unchanged.",
            **counts,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": False,
                "title": self.env._("Units imported"),
                "message": message,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _import_file(self):
        """Read, check, then write. Returns the counts."""
        rows = self._read_rows()
        values, errors = self._check_rows(rows)
        if errors:
            raise UserError(
                self.env._(
                    "Nothing was imported. Fix these rows and import the file "
                    "again:\n%(errors)s",
                    errors="\n".join(errors),
                )
            )
        return self._write_units(values)

    # ------------------------------------------------------------------
    # Reading: CSV and .xlsx give the same list of (row number, cells)
    # ------------------------------------------------------------------

    def _read_rows(self):
        """Return [(row_number, {column: cell})] for every non-empty data row.
        Row numbers are spreadsheet rows: the header is row 1."""
        name = (self.filename or "").lower()
        content = base64.b64decode(self.file or b"")
        if not content:
            raise UserError(self.env._("The file is empty."))
        if name.endswith(".csv"):
            table = self._read_csv(content)
        elif name.endswith(".xlsx"):
            table = self._read_xlsx(content)
        elif name.endswith(".xls"):
            raise UserError(
                self.env._("Old .xls files are not supported: save it as .xlsx.")
            )
        else:
            raise UserError(self.env._("Upload a .csv or .xlsx file."))
        return self._rows_by_header(table)

    def _read_csv(self, content):
        try:
            # utf-8-sig: Excel's "CSV UTF-8" starts with a byte order mark.
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise UserError(
                self.env._("The CSV file is not UTF-8: save it as CSV UTF-8.")
            ) from error
        return list(csv.reader(io.StringIO(text)))

    def _read_xlsx(self, content):
        try:
            # data_only: a formula is read as its last saved value (as
            # base_import does). Only the first sheet is read.
            book = openpyxl.load_workbook(
                io.BytesIO(content), read_only=True, data_only=True
            )
            sheet = book.worksheets[0]
            table = [list(row) for row in sheet.iter_rows(values_only=True)]
            book.close()
        except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as error:
            raise UserError(
                self.env._("The file is not a valid .xlsx file.")
            ) from error
        return table

    def _rows_by_header(self, table):
        if not table:
            raise UserError(self.env._("The file is empty."))
        header = [_cell_text(cell).lower() for cell in table[0]]
        if len(header) == 1 and ";" in header[0]:
            raise UserError(
                self.env._("Columns must be separated by commas, not semicolons.")
            )
        missing = [column for column in REQUIRED_COLUMNS if column not in header]
        unknown = [column for column in header if column and column not in COLUMNS]
        if missing or unknown:
            raise UserError(
                self.env._(
                    "Row 1 (header): missing columns: %(missing)s; unknown "
                    "columns: %(unknown)s. Expected: %(expected)s.",
                    missing=", ".join(missing) or "-",
                    unknown=", ".join(unknown) or "-",
                    expected=", ".join(COLUMNS),
                )
            )
        rows = []
        for number, cells in enumerate(table[1:], start=2):
            if all(_cell_text(cell) == "" for cell in cells):
                continue  # an empty row is skipped but keeps its number
            row = {
                column: cells[index] if index < len(cells) else None
                for index, column in enumerate(header)
                if column
            }
            rows.append((number, row))
        if not rows:
            raise UserError(self.env._("The file has no units after the header."))
        return rows

    # ------------------------------------------------------------------
    # Phase 1: check every row, write nothing
    # ------------------------------------------------------------------

    def _check_rows(self, rows):
        """Return (values per row, errors). Every bad row gives one error
        line 'Row N: reason; reason'."""
        company = self.env.company
        project_codes = {_cell_text(row.get("project_code")) for _number, row in rows}
        projects = {
            project.code: project
            for project in self.env["real.estate.project"].search(
                [("company_id", "=", company.id), ("code", "in", list(project_codes))]
            )
        }
        unit_types = self._unit_types()
        first_row_of_code = {}
        values, errors = [], []
        for number, row in rows:
            vals, reasons = self._check_row(row, projects, unit_types)
            code = vals.get("code")
            if code in first_row_of_code:
                reasons.append(
                    self.env._(
                        "code %(code)s is already on row %(row)s",
                        code=code,
                        row=first_row_of_code[code],
                    )
                )
            elif code:
                first_row_of_code[code] = number
            if reasons:
                errors.append(
                    self.env._(
                        "Row %(row)s: %(reasons)s",
                        row=number,
                        reasons="; ".join(reasons),
                    )
                )
            else:
                values.append(vals)
        return values, errors

    def _check_row(self, row, projects, unit_types):
        reasons = []
        vals = {"code": _cell_text(row.get("code"))}
        if not vals["code"]:
            reasons.append(self.env._("code is empty"))

        project_code = _cell_text(row.get("project_code"))
        if project_code in projects:
            vals["project_id"] = projects[project_code]
        elif project_code:
            reasons.append(self.env._("unknown project %(code)s", code=project_code))
        else:
            reasons.append(self.env._("project_code is empty"))

        unit_type = _cell_text(row.get("unit_type")).lower()
        if unit_type in unit_types:
            vals["unit_type"] = unit_types[unit_type]
        else:
            reasons.append(
                self.env._(
                    "unit_type %(value)s is not one of %(allowed)s",
                    value=unit_type or "(empty)",
                    allowed=", ".join(sorted(set(unit_types.values()))),
                )
            )

        for column, minimum, strict in (("area", 0, True), ("list_price", 0, False)):
            number, reason = self._number(row.get(column), column)
            if reason:
                reasons.append(reason)
            elif number is None:
                reasons.append(self.env._("%(column)s is empty", column=column))
            elif number < minimum or (strict and number == minimum):
                reasons.append(
                    self.env._(
                        "%(column)s must be %(rule)s 0",
                        column=column,
                        rule=">" if strict else ">=",
                    )
                )
            else:
                vals[column] = number

        for column in OPTIONAL_COLUMNS:
            number, reason = self._number(row.get(column), column, integer=True)
            if reason:
                reasons.append(reason)
            else:
                vals[column] = int(number or 0)
        if vals.get("bedrooms", 0) < 0:
            reasons.append(self.env._("bedrooms cannot be negative"))
        return vals, reasons

    def _number(self, cell, column, integer=False):
        """Return (number or None, error or None). A comma is refused, not
        guessed: in '8,580,000' it is a thousands separator, elsewhere a
        decimal point."""
        if isinstance(cell, bool):
            return None, self.env._("%(column)s is not a number", column=column)
        if isinstance(cell, int | float):
            number = cell
        else:
            text = _cell_text(cell).replace(" ", "")
            if not text:
                return None, None
            if "," in text:
                return None, self.env._(
                    "%(column)s %(value)s: write numbers without commas",
                    column=column,
                    value=text,
                )
            try:
                number = float(text)
            except ValueError:
                return None, self.env._(
                    "%(column)s %(value)s is not a number", column=column, value=text
                )
        if integer and number != int(number):
            return None, self.env._(
                "%(column)s %(value)s must be a whole number",
                column=column,
                value=number,
            )
        return number, None

    def _unit_types(self):
        """Accept the key (twin_house) or the label (Twin House), any case."""
        selection = self.env["real.estate.unit"]._fields["unit_type"].selection
        types = {}
        for key, label in selection:
            types[key] = key
            types[label.lower()] = key
        return types

    # ------------------------------------------------------------------
    # Phase 2: only when every row is right
    # ------------------------------------------------------------------

    def _write_units(self, values):
        Unit = self.env["real.estate.unit"]
        company = self.env.company
        # BR-01: the code is the key inside the company; archived units count,
        # so an archived unit is updated (and made active), never duplicated.
        existing = {
            unit.code: unit
            for unit in Unit.with_context(active_test=False).search(
                [
                    ("company_id", "=", company.id),
                    ("code", "in", [vals["code"] for vals in values]),
                ]
            )
        }
        counts = {"created": 0, "updated": 0, "unchanged": 0}
        to_create = []
        for vals in values:
            unit = existing.get(vals["code"])
            if not unit:
                to_create.append(dict(vals, project_id=vals["project_id"].id))
                continue
            changes = _changes(unit, vals)
            if changes:
                unit.write(changes)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
        if to_create:
            Unit.create(to_create)
            counts["created"] = len(to_create)
        return counts


def _cell_text(cell):
    """A cell as stripped text. Excel gives 302.0 for 302, so whole floats
    lose their '.0'."""
    if cell is None:
        return ""
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)
    return str(cell).strip()


def _changes(unit, vals):
    """Only the fields whose value differs, so an unchanged unit is not written."""
    changes = {}
    if unit.project_id != vals["project_id"]:
        changes["project_id"] = vals["project_id"].id
    for field in FLOAT_FIELDS:
        if float_compare(unit[field], vals[field], precision_digits=2):
            changes[field] = vals[field]
    for field in PLAIN_FIELDS:
        if unit[field] != vals[field]:
            changes[field] = vals[field]
    if not unit.active:
        changes["active"] = True
    return changes
