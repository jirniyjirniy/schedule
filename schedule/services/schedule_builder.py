from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

ROUND = Decimal("0.01")


@dataclass
class Periodicity:
    value: int
    unit: str  # 'd', 'w', 'm'

    def add(self, dt: date) -> date:
        if self.unit == "d":
            return dt + relativedelta(days=self.value)
        if self.unit == "w":
            return dt + relativedelta(weeks=self.value)
        if self.unit == "m":
            return dt + relativedelta(months=self.value)
        raise ValueError("Unsupported periodicity unit")


def parse_periodicity(s: str) -> Periodicity:
    # e.g. "1m", "5d", "2w"
    if not s or len(s) < 2:
        raise ValueError("Invalid periodicity format")
    value = int(s[:-1])
    unit = s[-1]
    if unit not in ("d", "w", "m"):
        raise ValueError("Invalid periodicity unit; use 'd', 'w', or 'm'")
    return Periodicity(value=value, unit=unit)  # теперь поле unit существует


def qround(x: Decimal) -> Decimal:
    return x.quantize(ROUND, rounding=ROUND_HALF_UP)


def build_declining_balance_schedule(
    *, amount: Decimal, start_date: date, payments: int, periodicity: Periodicity,
    rate_per_period: Decimal
):
    """
    Declining balance with equal principal portions by default.
    interest_i = outstanding_before_i * rate_per_period
    principal_i ~ amount/payments (last one adjusted by rounding).
    """
    principal_base = qround(amount / Decimal(payments))

    schedule = []
    outstanding = amount
    current_date = periodicity.add(start_date)  # first due after start

    total_principal = Decimal("0")

    for i in range(1, payments + 1):
        # last principal adjusted to clear outstanding
        principal = principal_base if i < payments else qround(outstanding)
        if principal > outstanding:
            principal = outstanding
        interest = qround(outstanding * rate_per_period)

        new_outstanding = qround(outstanding - principal)

        schedule.append({
            "seq": i,
            "date": current_date,
            "principal": principal,
            "interest": interest,
            "out_before": qround(outstanding),
            "out_after": new_outstanding,
        })

        total_principal += principal
        outstanding = new_outstanding
        current_date = periodicity.add(current_date)

    # final correction if tiny rounding residuals remain
    if outstanding != Decimal("0.00"):
        diff = qround(outstanding)
        if diff != 0:
            schedule[-1]["principal"] = qround(schedule[-1]["principal"] + diff)
            schedule[-1]["out_after"] = qround(schedule[-1]["out_after"] - diff)

    return schedule


def recalc_after_change(
    existing, changed_seq: int, new_principal: Decimal, rate_per_period: Decimal,
    periodicity: Periodicity
):
    """
    existing: list of dicts like build_declining_balance_schedule() output
    Rule: lock the changed payment's principal to new_principal; keep other principals as-is,
    then recompute interest from this payment onward based on new outstanding.
    Any residual principal (positive or negative) is absorbed by the LAST payment's principal.
    """
    from copy import deepcopy
    schedule = deepcopy(existing)

    # apply change
    idx = changed_seq - 1
    if idx < 0 or idx >= len(schedule):
        raise ValueError("Invalid payment seq")

    schedule[idx]["principal"] = qround(new_principal)

    # recompute outstanding forward
    # first, compute outstanding before changed payment from previous entry
    if idx == 0:
        out_before = schedule[0]["out_before"]
    else:
        out_before = schedule[idx - 1]["out_after"]
    schedule[idx]["out_before"] = qround(out_before)
    schedule[idx]["interest"] = qround(out_before * rate_per_period)
    out_after = qround(out_before - schedule[idx]["principal"])
    schedule[idx]["out_after"] = out_after

    # for next payments, keep principal amounts but update interests & outstandings
    for j in range(idx + 1, len(schedule)):
        schedule[j]["out_before"] = out_after
        schedule[j]["interest"] = qround(out_after * rate_per_period)
        # keep previously planned principal (unless it exceeds outstanding)
        principal = min(schedule[j]["principal"], out_after)
        schedule[j]["principal"] = qround(principal)
        out_after = qround(out_after - schedule[j]["principal"])
        schedule[j]["out_after"] = out_after

    # absorb any residual in the last payment's principal
    if out_after != Decimal("0.00"):
        schedule[-1]["principal"] = qround(schedule[-1]["principal"] + out_after)
        schedule[-1]["out_after"] = qround(schedule[-1]["out_after"] - out_after)
        out_after = schedule[-1]["out_after"]

    # sanity
    if out_after < Decimal("0"):
        raise ValueError("Principal over-reduced; schedule would overpay the loan")

    return schedule
