from odoo import fields, models


class RealEstateScheduleGenerate(models.TransientModel):
    """US-02: the agent picks a plan and generates the contract's schedule.
    Same shape as the cancel dialog; the work is in the contract's
    _generate_schedule(), so the rules hold whoever calls it."""

    _name = "real.estate.schedule.generate"
    _description = "Generate a Payment Schedule"
    _check_company_auto = True

    contract_id = fields.Many2one(
        "real.estate.contract", required=True, readonly=True, ondelete="cascade"
    )
    company_id = fields.Many2one(related="contract_id.company_id")
    # BR-14: a plan of the contract's company (check_company).
    plan_id = fields.Many2one(
        "real.estate.plan.template",
        string="Payment Plan",
        required=True,
        check_company=True,
    )

    def action_generate(self):
        self.ensure_one()
        self.contract_id._generate_schedule(self.plan_id)
        return {"type": "ir.actions.act_window_close"}
