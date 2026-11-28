from odoo import fields, models


def _post_needs_write_for_customers(records, message_operation):
    """BR-56: customers only read their reservations and contracts. Odoo lets
    anyone who can read these records post on their chatter (their
    ``_mail_post_access`` is "read", for staff); for a user who is not an
    employee, posting needs write access, which customers do not have.
    Staff keep the real_estate_eg rule."""
    if message_operation == "create" and not records.env.user._is_internal():
        return dict.fromkeys(records, "write")
    return None


class RealEstateReservation(models.Model):
    """BR-57: the identity a customer types with a portal request. Kept on the
    request, not written to the contact: the agent checks it against the card
    when they call the customer and copies it to the contact (BR-05, BR-06),
    so the portal never edits contacts and never says whether a number is
    already known."""

    _inherit = "real.estate.reservation"

    customer_nationality = fields.Selection(
        [("egyptian", "Egyptian"), ("foreign", "Foreign")],
        string="Nationality (portal)",
        readonly=True,
        copy=False,
    )
    customer_national_id = fields.Char(
        string="National ID (portal)", readonly=True, copy=False
    )
    customer_passport_number = fields.Char(
        string="Passport Number (portal)", readonly=True, copy=False
    )
    # BR-56: the notes of the agent's call are for staff, not for the customer
    # (employees are all in base.group_user, so staff see no change).
    note = fields.Text(groups="base.group_user")

    def _mail_get_operation_for_mail_message_operation(self, message_operation):
        return _post_needs_write_for_customers(
            self, message_operation
        ) or super()._mail_get_operation_for_mail_message_operation(message_operation)


class RealEstateContract(models.Model):
    _inherit = "real.estate.contract"

    # BR-56: the collections flag (BR-31) is internal.
    at_risk = fields.Boolean(groups="base.group_user")

    def _mail_get_operation_for_mail_message_operation(self, message_operation):
        return _post_needs_write_for_customers(
            self, message_operation
        ) or super()._mail_get_operation_for_mail_message_operation(message_operation)
