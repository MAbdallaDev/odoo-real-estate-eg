"""US-02: the schedule arithmetic, as a pure function (no ORM).

Written by the maintainer (Story 03, Step 5). Its tests come first:
tests/test_schedule_math.py says what "correct" means.

Rules: BR-15 (down payment), BR-16 (installments, last one absorbs the
rounding difference), BR-17 (due dates from the contract date, month-end
clamping), BR-18 (maintenance deposit), BR-20 (cash plan), BR-45 (exact
decimal arithmetic, half up to whole EGP).
"""


def compute_schedule(
    price,  # contract price, whole EGP
    contract_date,  # datetime.date
    down_payment_percent,  # 10 means 10 %
    installment_count,  # N; 0 for a cash plan
    step_months,  # 1, 3, 6 or 12
    first_installment_months,  # months from the contract date to installment 1
    maintenance_percent,  # 8 means 8 %
    maintenance_at_signing,  # True: due on the contract date; False: no date yet
):
    """Return a list of dicts, in order: the down payment, installments 1..N,
    the maintenance deposit. Keys: line_type ("down_payment" | "installment" |
    "maintenance"), number (k for installments, 0 otherwise), amount (int, whole
    EGP), date_due (datetime.date or None). A down payment or deposit of 0 is
    left out."""
    raise NotImplementedError("Step 5: the maintainer writes this function.")
