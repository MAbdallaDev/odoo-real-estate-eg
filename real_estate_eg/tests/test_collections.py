from ast import literal_eval

from freezegun import freeze_time

from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestCollections(RealEstateCommon):
    """US-04 / BR-26 / BR-31 / BR-37: the collections screens."""

    def test_bucket_edges(self):
        """T1. BR-37: installment 1 is due 10 Apr 2027; the nightly job
        moves it from bucket to bucket. Days 1-7 are the grace period, so
        the first bucket starts at day 8."""
        contract, line = self._installment_1_invoiced()
        for day, days, bucket in (
            ("2027-04-17", 7, False),
            ("2027-04-18", 8, "1_30"),
            ("2027-05-10", 30, "1_30"),
            ("2027-05-11", 31, "31_60"),
            ("2027-06-09", 60, "31_60"),
            ("2027-06-10", 61, "61_90"),
            ("2027-07-09", 90, "61_90"),
            ("2027-07-10", 91, "over_90"),
        ):
            self._night(day)
            self.assertEqual(line.days_past_due, days, day)
            self.assertEqual(line.aging_bucket, bucket, day)
        # Collections read it, and the project to group by, without rights
        # on invoices.
        line_as_collections = line.with_user(self.collections)
        self.assertEqual(line_as_collections.aging_bucket, "over_90")
        self.assertEqual(line_as_collections.project_id, self.project)

    def test_bucket_cleared_by_payment(self):
        """T2. BR-26 / BR-37: paying an overdue line clears the bucket at
        once, without waiting for the next nightly run."""
        __, line = self._installment_1_invoiced()
        self._night("2027-05-11")
        self.assertEqual(line.aging_bucket, "31_60")
        self._pay(line, 241_313, "2027-05-12")
        self.assertFalse(line.is_overdue)
        self.assertFalse(line.aging_bucket)

    # ------------------------------------------------------------------
    # AC-04.1 / AC-04.2: the two lists, through their actions' domains
    # ------------------------------------------------------------------

    def _domain(self, xmlid):
        return literal_eval(self.env.ref("real_estate_eg." + xmlid).domain)

    def _search(self, user, xmlid):
        Line = self.env["real.estate.installment"].with_user(user)
        return Line.search(self._domain(xmlid))

    def _two_contracts(self):
        """Agent A's Example A with installment 1 invoiced on 10 Apr 2027,
        agent B's contract on the 2-bedroom unit confirmed the same day as A
        (installment 1 due 10 Apr, not invoiced), and a draft of agent A's
        with a line due 10 Apr too. Returns both installment 1 lines."""
        self.customer_eg.phone = "+20 100 555 0101"
        contract_b = self.add_schedule(
            self.create_contract(user=self.agent_b, unit=self.unit_2br),
            "2027-01-10",
        )
        with freeze_time("2027-01-10"):
            self._confirmed(contract_b)
        self.add_schedule(
            self.create_contract(unit=self.make_unit("HNC-B07-0303")), "2027-01-10"
        )
        contract_a, line_a = self._installment_1_invoiced()
        line_b = contract_b.installment_ids.filtered(lambda x: x.number == 1)
        return contract_a, line_a, contract_b, line_b

    def test_ac_04_1_due_this_month(self):
        """T3. AC-04.1: every unpaid line due this month (invoiced or not) of
        a confirmed contract, with customer, phone, unit, amount and agent;
        not a draft's line, not a paid one, not another month's."""
        __, line_a, __, line_b = self._two_contracts()
        action = "real_estate_installment_action_due"
        with freeze_time("2027-03-31"):
            self.assertFalse(self._search(self.collections, action))
        with freeze_time("2027-05-01"):
            self.assertFalse(self._search(self.collections, action))
        with freeze_time("2027-04-15"):
            self.assertEqual(self._search(self.collections, action), line_a | line_b)
        line = line_a.with_user(self.collections)
        self.assertEqual(line.partner_id, self.customer_eg)
        self.assertEqual(line.partner_phone, "+20 100 555 0101")
        self.assertEqual(line.unit_id, self.unit_3br)
        self.assertEqual(line.amount, 241_313)
        self.assertEqual(line.user_id, self.agent_a)
        self._pay(line_a, 241_313, "2027-04-15")
        with freeze_time("2027-04-15"):
            self.assertEqual(self._search(self.collections, action), line_b)

    def _overdue_on_18_april(self):
        """Down payments paid on time; the nightly job of 18 Apr 2027 makes
        A's installment 1 overdue (8 days). B's installment 1 is invoiced
        that night, so its effective due date is 18 Apr: not overdue."""
        contract_a, line_a, contract_b, line_b = self._two_contracts()
        for contract in contract_a | contract_b:
            down_payment = self._line(contract, "down_payment")
            self._pay(down_payment, down_payment.amount, "2027-01-10")
        self._night("2027-04-18")
        return line_a, line_b

    def test_ac_04_2_overdue_list(self):
        """T4. AC-04.2: exactly the overdue lines, with days past due and
        the accrued late fee, read by collections."""
        line_a, line_b = self._overdue_on_18_april()
        overdue = self._search(
            self.collections, "real_estate_installment_action_overdue"
        )
        self.assertEqual(overdue, line_a)
        self.assertEqual(overdue.days_past_due, 8)
        self.assertGreater(overdue.late_fee_display, 0)
        self.assertEqual(overdue.aging_bucket, "1_30")
        self.assertFalse(line_b.is_overdue)

    def test_lists_follow_record_rules(self):
        """T5. BR-35: the lists add no rule and no sudo(). Agent B does not
        see agent A's overdue line; A, the manager and the accountant do."""
        line_a, line_b = self._overdue_on_18_april()
        overdue = "real_estate_installment_action_overdue"
        self.assertFalse(self._search(self.agent_b, overdue))
        for user in (self.agent_a, self.manager, self.accountant):
            self.assertEqual(self._search(user, overdue), line_a, user.login)
        with freeze_time("2027-04-15"):
            due = "real_estate_installment_action_due"
            self.assertEqual(self._search(self.agent_b, due), line_b)
            self.assertEqual(self._search(self.agent_a, due), line_a)

    # ------------------------------------------------------------------
    # AC-04.3: the pivot
    # ------------------------------------------------------------------

    def test_ac_04_3_pivot(self):
        """T6. AC-04.3: overdue amounts by project x aging bucket, as the
        pivot reads them (formatted_read_group), as collections. On 11 May
        2027 A's installment 1 (Horizon New Cairo) is 31 days past due and
        B's (a second project, invoiced 18 Apr) is 23."""
        project_2 = self.env["real.estate.project"].create(
            {"name": "Nile Gardens", "code": "NG", "location": "Sheikh Zayed"}
        )
        self.unit_2br.project_id = project_2
        line_a, line_b = self._overdue_on_18_april()
        self._night("2027-05-11")
        groups = (
            self.env["real.estate.installment"]
            .with_user(self.collections)
            .formatted_read_group(
                self._domain("real_estate_installment_action_analysis"),
                ["project_id", "aging_bucket"],
                ["amount_residual:sum"],
            )
        )
        cells = {
            (group["project_id"][0], group["aging_bucket"]): group[
                "amount_residual:sum"
            ]
            for group in groups
        }
        self.assertEqual(
            cells,
            {
                (self.project.id, "31_60"): 241_313,
                (project_2.id, "1_30"): line_b.amount,
            },
        )

    # ------------------------------------------------------------------
    # S07.3: the index ships with the module
    # ------------------------------------------------------------------

    def test_s07_3_index_installed(self):
        """T7. S07.3: the Overdue list's partial index exists after install,
        with its definition from the model, next to Story 05's plain index
        on is_overdue. Small tables are scanned whatever the indexes: this
        checks that it exists, not that it is used (measured on re_perf)."""
        self.env.cr.execute(
            "SELECT indexname, indexdef FROM pg_indexes"
            " WHERE tablename = 'real_estate_installment'"
        )
        indexes = dict(self.env.cr.fetchall())
        definition = indexes.get("real_estate_installment_overdue_order_idx", "")
        self.assertIn("days_past_due DESC, id", definition)
        self.assertIn("WHERE (is_overdue IS TRUE)", definition)
        self.assertIn("real_estate_installment__is_overdue_index", indexes)
