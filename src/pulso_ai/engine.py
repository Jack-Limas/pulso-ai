from collections import defaultdict
from collections.abc import Iterator

from pulso_ai.advice import Advisor, GeminiAdvisor, RuleAdvisor
from pulso_ai.anomalies import detect_anomalies
from pulso_ai.categorization import Categorizer, GeminiClassifier
from pulso_ai.config import Settings
from pulso_ai.domain import AnalysisInput, EntryKind, FinancialSummary, Report, Stage
from pulso_ai.forecast import forecast_liquidity
from pulso_ai.language_model import GeminiModel
from pulso_ai.patterns import find_ant_expenses, find_recurring


class AnalysisEngine:
    def __init__(self, categorizer: Categorizer, advisor: Advisor) -> None:
        self._categorizer = categorizer
        self._advisor = advisor

    def run(self, analysis: AnalysisInput) -> Iterator[Stage | Report]:
        entries = analysis.entries

        yield Stage.CATEGORIZING
        categorized = self._categorizer.categorize(entries, analysis.known_categories)

        yield Stage.DETECTING_ANOMALIES
        anomalies = detect_anomalies(entries, categorized, analysis.locale)

        yield Stage.FINDING_PATTERNS
        recurring = find_recurring(entries)
        ant_expenses = find_ant_expenses(entries, categorized)

        yield Stage.FORECASTING
        forecast = forecast_liquidity(entries, analysis.current_balance_cents)

        yield Stage.RECOMMENDING
        expense_by_category: dict[str, int] = defaultdict(int)
        amount_of = {entry.id: entry for entry in entries}
        for item in categorized:
            if amount_of[item.entry_id].kind is EntryKind.EXPENSE:
                expense_by_category[item.category] += amount_of[item.entry_id].amount_cents
        advice = self._advisor.advise(
            FinancialSummary(
                locale=analysis.locale,
                total_expense_cents=sum(expense_by_category.values()),
                expense_by_category=dict(expense_by_category),
                anomaly_count=len(anomalies),
                recurring_total_cents=sum(item.average_cents for item in recurring),
                ant_total_cents=sum(item.total_cents for item in ant_expenses),
                projected_cents=forecast.projected_cents,
            )
        )

        yield Report(categorized, anomalies, recurring, ant_expenses, forecast, advice)


def build_engine(settings: Settings) -> AnalysisEngine:
    rules = RuleAdvisor()
    if not settings.gemini_api_key:
        return AnalysisEngine(Categorizer(None), rules)
    model = GeminiModel(settings.gemini_api_key, settings.gemini_model)
    return AnalysisEngine(Categorizer(GeminiClassifier(model)), GeminiAdvisor(model, rules))
