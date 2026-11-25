"""US-05: the late-fee arithmetic, as pure functions (no ORM).

Rules: BR-26 (effective due date, days past due, overdue after the grace
period), BR-27 (a fee for every day from the effective due date until the day
the line is fully paid, on the amount unpaid that day, simple interest, never
rounded day by day), BR-28 (cap), BR-29 (computed from the payment history,
not added up night by night), BR-45 (exact decimal arithmetic).

The fee is a function of (amount, effective due date, payments, as-of date):
the same inputs always give the same answer, so the nightly job may run
twice, skip a night or see a payment entered late with an earlier date.
"""

from datetime import timedelta
from decimal import Decimal


def _dec(value):
    # Exact decimals: Decimal(str(x)), never Decimal(x) on a float.
    return value if isinstance(value, Decimal) else Decimal(str(value))


def days_past_due(effective_due, as_of):
    """BR-26: as-of date - effective due date, never below 0."""
    return max((as_of - effective_due).days, 0)


def paid_date(amount, payments):
    """The date the payments (a list of (date, amount)) reach `amount`, or
    None while the line is not fully paid."""
    target = _dec(amount)
    total = Decimal(0)
    for day, paid in sorted(payments):
        total += _dec(paid)
        if total >= target:
            return day
    return None


def compute_late_fee(
    amount,  # the line's amount
    effective_due,  # datetime.date: later of due date and invoice date (BR-26)
    payments,  # list of (datetime.date, amount): each payment from its own date
    as_of,  # datetime.date: the job's "today"
    monthly_rate,  # 1 means 1% per month (1/30 of it per day)
    cap_percent,  # 10 means at most 10% of the line
    grace_days,  # 7: overdue once more than this many days past due
):
    """The accrued late fee as an unrounded Decimal.

    A day d is charged when effective_due <= d < end, where end is the day the
    line was fully paid, or the as-of date while it is unpaid. Nothing is
    charged unless the line was overdue on some day: unpaid and more than
    grace_days past its effective due date."""
    amount = _dec(amount)
    # A payment dated after the as-of date is not known yet.
    by_day = {}
    for day, paid in payments:
        if day <= as_of:
            by_day[day] = by_day.get(day, Decimal(0)) + _dec(paid)
    fully_paid = paid_date(amount, by_day.items())
    end = fully_paid or as_of

    # BR-26 / BR-27: grace forgives the fee only if the line is paid inside it.
    last_unpaid_day = fully_paid - timedelta(days=1) if fully_paid else as_of
    if (last_unpaid_day - effective_due).days <= grace_days:
        return Decimal(0)

    # Sum unpaid(d) over the charged days, one segment per payment date.
    unpaid = amount - sum(
        (paid for day, paid in by_day.items() if day <= effective_due), Decimal(0)
    )
    start = effective_due
    amount_days = Decimal(0)
    for day in sorted(d for d in by_day if effective_due < d < end):
        amount_days += unpaid * (day - start).days
        unpaid -= by_day[day]
        start = day
    amount_days += unpaid * max((end - start).days, 0)

    # BR-27: one multiplication at the end, so no daily rounding can creep in.
    fee = amount_days * _dec(monthly_rate) / Decimal(100) / Decimal(30)
    # BR-28: the cap.
    return min(fee, amount * _dec(cap_percent) / Decimal(100))
