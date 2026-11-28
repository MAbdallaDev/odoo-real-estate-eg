from odoo import fields, models

from odoo.addons.real_estate_eg.models.real_estate_plan_template import (
    FREQUENCY_MONTHS,
)
from odoo.addons.real_estate_eg.tools.schedule import compute_schedule


class RealEstatePlanTemplate(models.Model):
    _inherit = "real.estate.plan.template"

    # BR-62: the reverse of Plans Offered; the portal rule shows customers
    # only the plans a project is sold with.
    project_ids = fields.Many2many(
        "real.estate.project",
        relation="real_estate_project_plan_template_rel",
        column1="plan_template_id",
        column2="project_id",
        string="Offered in Projects",
    )

    def _portal_preview(self, price):
        """BR-62: what this plan means for a unit at `price`, for the
        customer: the same numbers the schedule generator would give a
        contract signed today (compute_schedule of real_estate_eg, BR-15 to
        BR-18). Nothing is written. None when the price is too small for the
        plan (a line of 0 or less)."""
        self.ensure_one()
        lines = compute_schedule(
            price=price,
            contract_date=fields.Date.context_today(self),
            down_payment_percent=self.down_payment_percent,
            installment_count=self.installment_count,
            step_months=FREQUENCY_MONTHS.get(self.frequency, 0),
            first_installment_months=self.first_installment_months,
            maintenance_percent=self.maintenance_percent,
            maintenance_at_signing=self.maintenance_due == "signing",
        )
        if any(line["amount"] <= 0 for line in lines):
            return None

        def amount(line_type):
            return sum(
                line["amount"] for line in lines if line["line_type"] == line_type
            )

        installments = [line for line in lines if line["line_type"] == "installment"]
        return {
            "id": self.id,
            "name": self.name,
            "down_payment_percent": self.down_payment_percent,
            "down_payment": amount("down_payment"),
            "installment_count": len(installments),
            "frequency": self.frequency or None,
            "installment_amount": installments[0]["amount"] if installments else 0,
            # BR-16: the last installment absorbs the rounding.
            "last_installment_amount": (
                installments[-1]["amount"] if installments else 0
            ),
            "first_installment_months": (
                self.first_installment_months if installments else None
            ),
            "maintenance_percent": self.maintenance_percent,
            "maintenance": amount("maintenance"),
            "maintenance_due": self.maintenance_due or None,
            "total": sum(line["amount"] for line in lines),
        }
