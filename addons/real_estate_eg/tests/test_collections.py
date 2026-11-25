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
