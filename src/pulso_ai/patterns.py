from collections import defaultdict
from itertools import pairwise
from statistics import fmean

from pulso_ai.domain import AntExpense, CategorizedEntry, Entry, EntryKind, RecurringExpense

ANT_MAX_AMOUNT_CENTS = 2_000_000
ANT_MIN_COUNT = 4
RECURRING_MIN_OCCURRENCES = 2
RECURRING_CYCLES_DAYS = (7, 15, 30)
RECURRING_DAY_TOLERANCE = 3
RECURRING_AMOUNT_TOLERANCE = 0.2


def _expenses_by_merchant(entries: list[Entry]) -> dict[str, list[Entry]]:
    groups: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        if entry.kind is EntryKind.EXPENSE:
            groups[entry.merchant].append(entry)
    return groups


def find_ant_expenses(
    entries: list[Entry], categorized: list[CategorizedEntry]
) -> list[AntExpense]:
    category_of = {item.entry_id: item.category for item in categorized}
    findings = []
    for merchant, group in _expenses_by_merchant(entries).items():
        small = [entry for entry in group if entry.amount_cents <= ANT_MAX_AMOUNT_CENTS]
        if len(small) < ANT_MIN_COUNT:
            continue
        total = sum(entry.amount_cents for entry in small)
        dates = [entry.occurred_on for entry in small]
        findings.append(
            AntExpense(
                merchant=merchant,
                category=category_of.get(small[0].id, "other"),
                count=len(small),
                total_cents=total,
                average_cents=total // len(small),
                period_start=min(dates),
                period_end=max(dates),
            )
        )
    return sorted(findings, key=lambda finding: finding.total_cents, reverse=True)


def _matching_cycle(gaps: list[int]) -> int | None:
    for cycle in RECURRING_CYCLES_DAYS:
        if all(abs(gap - cycle) <= RECURRING_DAY_TOLERANCE for gap in gaps):
            return cycle
    return None


def find_recurring(entries: list[Entry]) -> list[RecurringExpense]:
    findings = []
    for merchant, group in _expenses_by_merchant(entries).items():
        if len(group) < RECURRING_MIN_OCCURRENCES:
            continue
        ordered = sorted(group, key=lambda entry: entry.occurred_on)
        gaps = [(b.occurred_on - a.occurred_on).days for a, b in pairwise(ordered)]
        cycle = _matching_cycle(gaps)
        average = fmean(entry.amount_cents for entry in ordered)
        stable = all(
            abs(entry.amount_cents - average) <= average * RECURRING_AMOUNT_TOLERANCE
            for entry in ordered
        )
        if cycle and stable:
            findings.append(RecurringExpense(merchant, round(average), cycle, len(ordered)))
    return findings
