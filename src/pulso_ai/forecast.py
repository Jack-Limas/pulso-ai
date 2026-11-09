from collections import defaultdict
from datetime import date

import numpy as np

from pulso_ai.domain import Entry, EntryKind, Forecast

HORIZON_DAYS = 30
MIN_DAYS_FOR_TREND = 2


def forecast_liquidity(entries: list[Entry], current_balance_cents: int) -> Forecast:
    """Projects the balance 30 days ahead at the average daily pace of the observed period."""
    if not entries:
        return Forecast(0, 0, current_balance_cents, 0)

    first = min(entry.occurred_on for entry in entries)
    last = max(entry.occurred_on for entry in entries)
    observed_days = (last - first).days + 1

    income = sum(entry.amount_cents for entry in entries if entry.kind is EntryKind.INCOME)
    expense = sum(entry.amount_cents for entry in entries if entry.kind is EntryKind.EXPENSE)
    expected_income = round(income / observed_days * HORIZON_DAYS)
    expected_expense = round(expense / observed_days * HORIZON_DAYS)

    return Forecast(
        expected_income_cents=expected_income,
        expected_expense_cents=expected_expense,
        projected_cents=current_balance_cents + expected_income - expected_expense,
        daily_trend_cents=_daily_trend(entries, first, observed_days),
    )


def _daily_trend(entries: list[Entry], first: date, observed_days: int) -> int:
    if observed_days < MIN_DAYS_FOR_TREND:
        return 0
    net_by_day: dict[int, int] = defaultdict(int)
    for entry in entries:
        sign = 1 if entry.kind is EntryKind.INCOME else -1
        net_by_day[(entry.occurred_on - first).days] += sign * entry.amount_cents
    daily_net = [net_by_day[day] for day in range(observed_days)]
    slope = np.polyfit(np.arange(observed_days), np.cumsum(daily_net), deg=1)[0]
    return round(float(slope))
