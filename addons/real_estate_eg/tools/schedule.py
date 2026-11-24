"""US-02: the schedule arithmetic, as a pure function (no ORM).

Written by the maintainer (Story 03, Step 5). Its tests come first:
tests/test_schedule_math.py says what "correct" means.

Rules: BR-15 (down payment), BR-16 (installments, last one absorbs the
rounding difference), BR-17 (due dates from the contract date, month-end
clamping), BR-18 (maintenance deposit), BR-20 (cash plan), BR-45 (exact
decimal arithmetic, half up to whole EGP).
"""

from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta


def half_up(value):
    """BR-45: a Decimal rounded half up to whole EGP, returned as int.
    858000.5 -> 858001 (Python's round() would give 858000)."""
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


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
    # Exact decimals from the start: Decimal(str(x)), never Decimal(x) on a float.
    price = Decimal(str(price))
    down_payment_percent = Decimal(str(down_payment_percent))
    maintenance_percent = Decimal(str(maintenance_percent))
    lines = []

    # BR-15: down payment, due on the contract date.
    down_payment = half_up(price * down_payment_percent / Decimal("100"))
    if down_payment:
        lines.append(
            {
                "line_type": "down_payment",
                "number": 0,
                "amount": down_payment,
                "date_due": contract_date,
            }
        )

    # BR-16: the rest split in N installments; the last one takes the remainder.
    if installment_count:
        rest = price - down_payment
        installment = half_up(rest / Decimal(str(installment_count)))
        for k in range(1, installment_count + 1):
            amount = installment
            if k == installment_count:
                amount = int(rest - installment * (installment_count - 1))
            # BR-17: always from the contract date, never from the previous
            # line, so 31 Jan gives 28 Feb, then 31 Mar (relativedelta clamps).
            months = first_installment_months + step_months * (k - 1)
            lines.append(
                {
                    "line_type": "installment",
                    "number": k,
                    "amount": amount,
                    "date_due": contract_date + relativedelta(months=months),
                }
            )

    # BR-18: maintenance deposit, not part of the price.
    maintenance = half_up(price * maintenance_percent / Decimal("100"))
    if maintenance:
        lines.append(
            {
                "line_type": "maintenance",
                "number": 0,
                "amount": maintenance,
                # Due at signing: the contract date; at delivery: no date yet.
                "date_due": contract_date if maintenance_at_signing else None,
            }
        )
    return lines
