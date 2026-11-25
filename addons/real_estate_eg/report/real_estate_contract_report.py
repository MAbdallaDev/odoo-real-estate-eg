from odoo import api, models

# BR-38: the Arabic words for the stored selection values, beside the
# English labels the fields already have. Words from the glossary
# (docs/business-requirements.md, Ch. 3). A value with no Arabic word here
# fails the report (KeyError), and test_report checks every value has one.
ARABIC_LABELS = {
    "unit_type": {
        "apartment": "شقة",
        "duplex": "دوبلكس",
        "chalet": "شاليه",
        "twin_house": "توين هاوس",
        "office": "مكتب",
        "retail": "محل",
    },
    "frequency": {
        "monthly": "شهري",
        "quarterly": "ربع سنوي",
        "semi_annual": "نصف سنوي",
        "annual": "سنوي",
    },
    "line_type": {
        "down_payment": "المقدم",
        "installment": "القسط",
        "maintenance": "وديعة الصيانة",
    },
    "maintenance_due": {
        "signing": "عند التوقيع",
        "delivery": "عند الاستلام",
    },
}

# Where each selection above lives, to read its English labels.
SELECTION_FIELDS = {
    "unit_type": ("real.estate.unit", "unit_type"),
    "frequency": ("real.estate.plan.template", "frequency"),
    "line_type": ("real.estate.installment", "line_type"),
    "maintenance_due": ("real.estate.plan.template", "maintenance_due"),
}


class ReportRealEstateContract(models.AbstractModel):
    """US-07: the values of the bilingual contract report. Odoo finds this
    model by its name, report.<report_name>, and calls _get_report_values()
    (same shape as report.account.report_invoice)."""

    _name = "report.real_estate_eg.report_contract"
    _description = "Bilingual Contract Report"

    @api.model
    def _english_labels(self):
        return {
            key: dict(self.env[model]._fields[field].selection)
            for key, (model, field) in SELECTION_FIELDS.items()
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            "doc_ids": docids,
            "doc_model": "real.estate.contract",
            "docs": self.env["real.estate.contract"].browse(docids),
            "en": self._english_labels(),
            "ar": ARABIC_LABELS,
        }
