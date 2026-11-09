from datetime import date
from uuid import uuid4

from pulso_ai.domain import CategorizedEntry, Entry, EntryKind, Method

DEFAULT_DAY = date(2026, 10, 5)


def expense(
    merchant: str = "TIENDA",
    amount_cents: int = 1_000_000,
    on: date = DEFAULT_DAY,
    description: str | None = None,
) -> Entry:
    text = description or merchant
    return Entry(uuid4().hex, on, text, merchant, EntryKind.EXPENSE, amount_cents)


def income(amount_cents: int, on: date = DEFAULT_DAY) -> Entry:
    return Entry(uuid4().hex, on, "NOMINA", "NOMINA", EntryKind.INCOME, amount_cents)


def as_category(entries: list[Entry], category: str = "food") -> list[CategorizedEntry]:
    return [CategorizedEntry(e.id, e.merchant, category, Method.RULE) for e in entries]
