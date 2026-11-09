from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class EntryKind(Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Method(Enum):
    RULE = "rule"
    MODEL = "model"


class Stage(Enum):
    CATEGORIZING = "categorizing"
    DETECTING_ANOMALIES = "detecting_anomalies"
    FINDING_PATTERNS = "finding_patterns"
    FORECASTING = "forecasting"
    RECOMMENDING = "recommending"


@dataclass(frozen=True)
class Entry:
    id: str
    occurred_on: date
    description: str
    merchant: str
    kind: EntryKind
    amount_cents: int


@dataclass(frozen=True)
class AnalysisInput:
    entries: list[Entry]
    current_balance_cents: int
    locale: str
    known_categories: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CategorizedEntry:
    entry_id: str
    merchant: str
    category: str
    method: Method


@dataclass(frozen=True)
class Anomaly:
    entry_id: str
    reason: str
    score: float


@dataclass(frozen=True)
class RecurringExpense:
    merchant: str
    average_cents: int
    interval_days: int
    occurrences: int


@dataclass(frozen=True)
class AntExpense:
    merchant: str
    category: str
    count: int
    total_cents: int
    average_cents: int
    period_start: date
    period_end: date


@dataclass(frozen=True)
class Forecast:
    expected_income_cents: int
    expected_expense_cents: int
    projected_cents: int
    daily_trend_cents: int


@dataclass(frozen=True)
class Advice:
    title: str
    detail: str


@dataclass(frozen=True)
class FinancialSummary:
    """Aggregates only: this is all a language model ever sees about the user's money."""

    locale: str
    total_expense_cents: int
    expense_by_category: dict[str, int]
    anomaly_count: int
    recurring_total_cents: int
    ant_total_cents: int
    projected_cents: int


@dataclass(frozen=True)
class Report:
    categorized: list[CategorizedEntry]
    anomalies: list[Anomaly]
    recurring: list[RecurringExpense]
    ant_expenses: list[AntExpense]
    forecast: Forecast
    advice: list[Advice]
