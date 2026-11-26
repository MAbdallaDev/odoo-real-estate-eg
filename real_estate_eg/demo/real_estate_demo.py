"""S10.1: demo contracts, payments and cheques for Nile Heights Developments.

Called once from demo/real_estate_demo.xml (a <function> tag), only when the
module is installed with demo data. Same pattern as account/demo/account_demo.py.

The demo replays about fifteen months of history, with dates counted back from
the install day, so the overdue and at-risk lists are never empty. It uses the
module's own methods, which take the day as a parameter: _invoice_due_lines(day)
and _cron_nightly(day). Only confirmation is replayed by hand (the state, its
date, and the invoices due that day), because action_confirm() always uses today.
"""

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

DEMO = "real_estate_eg.demo_"


class RealEstateContract(models.Model):
    _inherit = "real.estate.contract"

    @api.model
    def _demo_load(self):
        company = self.env.ref(DEMO + "company_nile_heights")
        Contract = self.with_context(allowed_company_ids=[company.id]).with_company(
            company
        )
        bank = Contract._demo_setup_accounting(company)
        today = fields.Date.context_today(Contract)
        ref = self.env.ref
        salma, karim = ref(DEMO + "user_salma"), ref(DEMO + "user_karim")
        omar, hoda = ref(DEMO + "user_omar"), ref(DEMO + "user_hoda")

        def contract(agent, unit, customer, plan, months_ago, days_ago=0):
            day = today - relativedelta(months=months_ago, days=days_ago)
            return Contract._demo_contract(agent, unit, customer, plan, day)

        # 1. Draft: signed three days ago, schedule generated, not confirmed.
        contract(salma, "hnc_b07_0401", "ahmed", "std_8q", 0, 3)

        # 2. Confirmed, every line paid on time (Example A's unit and plan).
        on_time = contract(salma, "hnc_b07_0302", "mona", "std_8q", 13)
        on_time._demo_confirm(omar)
        on_time._demo_history(bank, today, late={})

        # 3. Confirmed, installment 1 paid 20 days late, installment 2 unpaid
        #    for about 70 days: overdue and at risk (BR-31).
        at_risk = contract(karim, "pss_b01_0101", "youssef", "sahel_7q", 8, 10)
        at_risk._demo_confirm(omar)
        at_risk._demo_history(bank, today, late={1: 20, 2: None})

        # 4. Confirmed, installment 4 unpaid for 15 days: overdue, not at risk.
        overdue = contract(salma, "cbp_a02_0105", "delta", "biz_5m", 4, 15)
        overdue._demo_confirm(omar)
        overdue._demo_history(bank, today, late={4: None})

        # 5. Delivered 20 days ago; the maintenance deposit is invoiced on
        #    delivery and not paid yet.
        delivered = contract(karim, "hnc_b08_1201", "laila", "std_8q", 15)
        delivered._demo_confirm(omar)
        delivered._demo_history(bank, today - timedelta(days=21), late={})
        delivered.with_user(omar).write({"delivery_date": today - timedelta(days=20)})
        delivered.with_user(omar).action_deliver()

        # 6. Closed: a cash plan, paid, delivered, deposit paid, then closed by
        #    the nightly job (BR-12).
        closed = contract(salma, "pss_b05_0001", "james", "cash", 3)
        closed._demo_confirm(omar)
        closed._demo_history(bank, today, late={})
        closed.with_user(omar).write({"delivery_date": today - timedelta(days=30)})
        closed.with_user(omar).action_deliver()
        closed._demo_history(bank, today, late={})

        # 7. Cancelled after paying the down payment and two installments; the
        #    third was invoiced and not paid (BR-33, BR-34).
        cancelled = contract(karim, "hnc_b08_0101", "sherif", "ext_10q", 10)
        cancelled._demo_confirm(omar)
        cancelled._demo_history(bank, today, late={3: None})
        cancelled.with_user(omar)._cancel_with_reason(
            "The buyer withdrew before delivery (demo)."
        )

        # 8. Confirmed today: only the down payment is invoiced so far.
        new = contract(karim, "pss_b01_0102", "nadia", "sahel_7q", 0)
        new.with_user(omar).action_confirm()

        # The nightly job (§5.5) for today: late fees from the payment history,
        # the at-risk flag, and closing paid delivered contracts.
        Contract.sudo()._cron_nightly(today)
        # Hoda bills the at-risk contract's late fees (BR-30).
        at_risk.with_user(hoda).action_bill_late_fees()

        Contract._demo_cheques(hoda, on_time, at_risk, overdue, today)

    @api.model
    def _demo_setup_accounting(self, company):
        """The README's "Accounting setup" for the demo company: a chart, the
        three accounts, and Outstanding Receipts on the bank journal."""
        Chart = self.env["account.chart.template"].with_company(company)
        if not company.chart_template:
            # _load(), as account's res.company.create() does: try_loading()
            # only adds a check that warns while modules are still loading.
            Chart._load("generic_coa", company, install_demo=False)
            # The generic chart's fiscal country is the US, so it sets USD. The
            # company is Egyptian; nothing is posted yet, so both can change.
            # (A real Egyptian company would install l10n_eg instead.)
            company.write(
                {
                    "account_fiscal_country_id": self.env.ref("base.eg").id,
                    "currency_id": self.env.ref("base.EGP").id,
                }
            )
        Account = self.env["account.account"].with_company(company)

        def account(code, name, account_type):
            return Account.create(
                {
                    "code": code,
                    "name": name,
                    "account_type": account_type,
                    "company_ids": [Command.set(company.ids)],
                }
            )

        company.write(
            {
                "re_advance_account_id": account(
                    "212100", "Customer Advances", "liability_current"
                ).id,
                "re_maintenance_account_id": account(
                    "212200", "Maintenance Deposits", "liability_current"
                ).id,
                "re_late_fee_account_id": account(
                    "450100", "Late Fees", "income_other"
                ).id,
            }
        )
        bank = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "bank")], limit=1
        )
        outstanding = Chart.ref(
            "account_journal_payment_debit_account_id", raise_if_not_found=False
        )
        if not bank or not outstanding:
            raise UserError(
                self.env._("Demo data needs a bank journal and Outstanding Receipts.")
            )
        bank.inbound_payment_method_line_ids.filtered(
            lambda line: not line.payment_account_id
        ).payment_account_id = outstanding
        return bank

    @api.model
    def _demo_contract(self, agent, unit, customer, plan, day):
        """A draft created and scheduled by its agent, as in the UI."""
        contract = self.with_user(agent).create(
            {
                "partner_id": self.env.ref(DEMO + "customer_" + customer).id,
                "unit_id": self.env.ref(DEMO + "unit_" + unit).id,
                "user_id": agent.id,
                "date": day,
            }
        )
        contract._generate_schedule(self.env.ref(DEMO + "plan_" + plan))
        return contract

    def _demo_confirm(self, manager):
        """action_confirm() as it ran on the contract date: the same checks,
        the state and its date, and the lines due that day invoiced (BR-21)."""
        self.ensure_one()
        contract = self.with_user(manager)
        error = contract._confirmation_error_message()
        if error:
            raise UserError(error)
        contract.write({"state": "confirmed", "confirmation_date": self.date})
        contract._invoice_due_lines(self.date)

    def _demo_history(self, bank, until, late):
        """Invoice each line on its due date (as the nightly job did) up to
        `until`, and pay it. `late` maps an installment number to the days it
        was paid late, or None for never paid; other lines are paid 2 days
        after their due date, inside the grace period (no late fee)."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        accountant = self.env.ref(DEMO + "user_tarek")
        Register = (
            self.env["account.payment.register"]
            .with_user(accountant)
            .with_company(self.company_id)
        )
        lines = self.installment_ids.filtered(
            lambda x: x.date_due and x.date_due <= until
        )
        for line in lines.sorted(lambda x: (x.date_due, x.id)):
            self._invoice_due_lines(line.date_due)
            invoice = line.sudo().invoice_id
            delay = late.get(line.number, 2) if line.line_type == "installment" else 2
            if delay is None or not invoice or invoice.payment_state != "not_paid":
                continue
            pay_day = min(
                max(line.date_due, invoice.invoice_date) + timedelta(days=delay), today
            )
            # The accountant registers the payment, as in real life (BR-24).
            Register.with_context(
                active_model="account.move", active_ids=invoice.ids
            ).create(
                {"payment_date": pay_day, "journal_id": bank.id}
            ).action_create_payments()

    @api.model
    def _demo_cheques(self, officer, on_time, at_risk, overdue, today):
        """US-13: cheques in every state, recorded by the collections officer."""
        Cheque = self.env["real.estate.cheque"].with_user(officer)

        def line(contract, number):
            return contract.installment_ids.filtered(
                lambda x: x.line_type == "installment" and x.number == number
            )

        def cheque(number, bank_name, schedule_line, day):
            return Cheque.create(
                {
                    "name": number,
                    "bank_name": bank_name,
                    "date": day,
                    "amount": schedule_line.amount,
                    "line_id": schedule_line.id,
                }
            )

        # On time: installment 4 by a cleared cheque; 5 and 6 held for later.
        paid = cheque(
            "DEMO-100104",
            "Fictional Bank of Egypt",
            line(on_time, 4),
            line(on_time, 4).date_due,
        )
        paid.action_deposit()
        paid.action_clear()
        for number in (5, 6):
            schedule_line = line(on_time, number)
            cheque(
                f"DEMO-10010{number}",
                "Fictional Bank of Egypt",
                schedule_line,
                schedule_line.date_due,
            )

        # At risk: installment 2's cheque bounced; the replacement is held and
        # dated three days ago, so it is in To Deposit.
        bounced = cheque(
            "DEMO-200102",
            "Demo Commercial Bank",
            line(at_risk, 2),
            line(at_risk, 2).date_due,
        )
        bounced.action_deposit()
        bounced.action_bounce()
        cheque(
            "DEMO-200103",
            "Demo Commercial Bank",
            line(at_risk, 2),
            today - timedelta(days=3),
        )

        # Overdue: installment 4's cheque is deposited; the line stays overdue
        # until accounting records a payment (BR-42).
        deposited = cheque(
            "DEMO-300104",
            "Fictional Bank of Egypt",
            line(overdue, 4),
            line(overdue, 4).date_due,
        )
        deposited.action_deposit()
