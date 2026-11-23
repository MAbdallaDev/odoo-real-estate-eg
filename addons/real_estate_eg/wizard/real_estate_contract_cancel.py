from odoo import fields, models


class RealEstateContractCancel(models.TransientModel):
    """BR-32: a confirmed contract is cancelled only by a manager, with a
    written reason. A transient model: the record lives only while the dialog
    is open; the reason is stored on the contract."""

    _name = "real.estate.contract.cancel"
    _description = "Cancel a Confirmed Contract"

    contract_id = fields.Many2one(
        "real.estate.contract", required=True, readonly=True, ondelete="cascade"
    )
    reason = fields.Text(required=True)

    def action_confirm_cancel(self):
        self.ensure_one()
        self.contract_id._cancel_with_reason(self.reason)
        return {"type": "ir.actions.act_window_close"}
