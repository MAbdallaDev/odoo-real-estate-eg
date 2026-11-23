from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# BR-09: the only states. Same shape as SALE_ORDER_STATE in sale/models/sale_order.py.
CONTRACT_STATE = [
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
    ("delivered", "Delivered"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]


class RealEstateContract(models.Model):
    _name = "real.estate.contract"
    _description = "Real Estate Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # chatter and activities
    _check_company_auto = True
    _order = "id desc"

    # BR-07: reference from a sequence, set in create().
    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        index="trigram",
        default=lambda self: self.env._("New"),
    )
    # BR-07: one customer, one unit, one sales agent.
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
        check_company=True,
    )
    unit_id = fields.Many2one(
        "real.estate.unit",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    project_id = fields.Many2one(related="unit_id.project_id", store=True)
    user_id = fields.Many2one(
        "res.users",
        string="Sales Agent",
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
    )
    # The contract's company is its unit's company.
    company_id = fields.Many2one(related="unit_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    # BR-07: set on the draft; checked and filled on confirmation (Step 9).
    date = fields.Date(string="Contract Date", tracking=True, copy=False)
    confirmation_date = fields.Date(readonly=True, copy=False)
    delivery_date = fields.Date(readonly=True, copy=False, tracking=True)
    cancel_reason = fields.Text(readonly=True, copy=False)
    # BR-08: frozen at the unit's list price; depends on unit_id only.
    price = fields.Monetary(
        compute="_compute_price", store=True, precompute=True, tracking=True
    )
    state = fields.Selection(
        CONTRACT_STATE,
        string="Status",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        default="draft",
    )

    # BR-04 in the database: at most one contract per unit that is not
    # cancelled. Holds even when two users save at the same moment.
    _unit_live_unique = models.UniqueIndex(
        "(unit_id) WHERE state != 'cancelled'",
        "This unit already has a contract that is not cancelled.",
    )

    @api.depends("unit_id")
    def _compute_price(self):
        # Not "unit_id.list_price": a later list price change must not reach
        # existing contracts (AC-01.2). A new unit re-takes its price (AC-01.6).
        for contract in self:
            contract.price = contract.unit_id.list_price

    def _check_unit_free(self, unit_ids):
        """BR-04 / AC-01.3: a clear message before the database refuses.

        It names only the existing contract's reference (no customer, agent or
        price). sudo(): from Story 06 an agent cannot see another agent's
        contract, but the unit is still taken.
        """
        if len(unit_ids) != len(set(unit_ids)):
            raise ValidationError(self.env._("Two contracts cannot share one unit."))
        live = self.sudo().search(
            [
                ("unit_id", "in", unit_ids),
                ("state", "!=", "cancelled"),
                ("id", "not in", self.ids),
            ],
            limit=1,
        )
        if live:
            raise ValidationError(
                self.env._(
                    "Unit %(unit)s already has contract %(reference)s.",
                    unit=live.unit_id.code,
                    reference=live.name,
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        # BR-04: refuse a taken unit before drawing a reference (AC-01.3).
        self._check_unit_free(
            [vals["unit_id"] for vals in vals_list if vals.get("unit_id")]
        )
        # Same pattern as sale.order.create(): draw the reference from the
        # sequence, dated by the contract date so the year matches it.
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                unit = self.env["real.estate.unit"].browse(vals.get("unit_id"))
                vals["name"] = self.env["ir.sequence"].with_company(
                    unit.company_id
                ).next_by_code(
                    "real.estate.contract",
                    sequence_date=vals.get("date") or fields.Date.context_today(self),
                ) or self.env._("New")
        return super().create(vals_list)

    def write(self, vals):
        not_draft = self.filtered(lambda c: c.state != "draft")
        # BR-35: an agent edits a contract only while it is draft. A manager
        # edits all; system jobs run as superuser (env.su).
        if (
            not_draft
            and not self.env.su
            and not self.env.user.has_group("real_estate_eg.group_real_estate_manager")
        ):
            raise AccessError(
                self.env._(
                    "Only a sales manager can change a contract that is not draft."
                )
            )
        # BR-08 / BR-19: the unit, and so the price, is fixed once confirmed.
        if "unit_id" in vals and not_draft:
            raise UserError(
                self.env._("The unit can be changed only on a draft contract.")
            )
        if vals.get("unit_id"):
            # Writing one unit on several contracts would share it too.
            self._check_unit_free([vals["unit_id"]] * len(self))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft(self):
        # BR-13: same shape as sale.order's _unlink_except_draft_or_cancel.
        if any(contract.state != "draft" for contract in self):
            raise UserError(
                self.env._(
                    "Only draft contracts can be deleted. Cancel the contract instead."
                )
            )
