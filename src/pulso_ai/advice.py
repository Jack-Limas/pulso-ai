import json
import logging
from dataclasses import asdict
from typing import Protocol

from pulso_ai.domain import Advice, FinancialSummary
from pulso_ai.language_model import LanguageModel

logger = logging.getLogger(__name__)

MAX_ADVICE = 5
MAX_FIELD_LENGTH = 400
DOMINANT_CATEGORY_RATIO = 0.4

TEXTS = {
    "es": {
        "category": ("Reduce gastos en {name}", "{name} representa el {share}% de tus gastos."),
        "anomalies": ("Revisa movimientos inusuales", "Hay {count} transacciones marcadas."),
        "recurring": ("Revisa tus suscripciones", "Tus pagos periódicos suman {amount}."),
        "ant": ("Controla los gastos hormiga", "Tus gastos pequeños acumulan {amount}."),
        "negative": ("Ajusta tu presupuesto", "A este ritmo tu saldo proyectado es {amount}."),
    },
    "en": {
        "category": ("Cut spending on {name}", "{name} makes up {share}% of your expenses."),
        "anomalies": ("Review unusual activity", "{count} transactions were flagged."),
        "recurring": ("Review your subscriptions", "Recurring payments add up to {amount}."),
        "ant": ("Watch small purchases", "Small purchases add up to {amount}."),
        "negative": ("Adjust your budget", "At this pace your projected balance is {amount}."),
    },
}


CATEGORY_NAMES = {
    "es": {
        "food": "alimentación",
        "transport": "transporte",
        "housing": "vivienda",
        "entertainment": "entretenimiento",
        "utilities": "servicios",
        "health": "salud",
        "education": "educación",
        "technology": "tecnología",
        "shopping": "compras",
        "other": "otros",
    },
    "en": {"utilities": "utilities", "other": "other"},
}


def _money(cents: int, locale: str) -> str:
    sign = "-" if cents < 0 else ""
    text = f"{sign}${abs(cents) / 100:,.0f}"
    return text.replace(",", ".") if locale == "es" else text


class Advisor(Protocol):
    def advise(self, summary: FinancialSummary) -> list[Advice]: ...


class RuleAdvisor:
    def advise(self, summary: FinancialSummary) -> list[Advice]:
        texts = TEXTS.get(summary.locale, TEXTS["es"])

        def money(cents: int) -> str:
            return _money(cents, summary.locale)

        def build(key: str, **values: object) -> Advice:
            title, detail = texts[key]
            return Advice(title.format(**values), detail.format(**values))

        advice = []
        if summary.total_expense_cents and summary.expense_by_category:
            name, total = max(summary.expense_by_category.items(), key=lambda item: item[1])
            share = total / summary.total_expense_cents
            if share >= DOMINANT_CATEGORY_RATIO:
                label = CATEGORY_NAMES.get(summary.locale, {}).get(name, name)
                advice.append(build("category", name=label, share=round(share * 100)))
        if summary.anomaly_count:
            advice.append(build("anomalies", count=summary.anomaly_count))
        if summary.recurring_total_cents:
            advice.append(build("recurring", amount=money(summary.recurring_total_cents)))
        if summary.ant_total_cents:
            advice.append(build("ant", amount=money(summary.ant_total_cents)))
        if summary.projected_cents < 0:
            advice.append(build("negative", amount=money(summary.projected_cents)))
        return advice[:MAX_ADVICE]


class GeminiAdvisor:
    """Writes personalized advice, and falls back to the rules if the model fails."""

    def __init__(self, model: LanguageModel, fallback: Advisor) -> None:
        self._model = model
        self._fallback = fallback

    def advise(self, summary: FinancialSummary) -> list[Advice]:
        try:
            return self._ask_model(summary) or self._fallback.advise(summary)
        except Exception:
            logger.exception("Model advice failed")
            return self._fallback.advise(summary)

    def _ask_model(self, summary: FinancialSummary) -> list[Advice]:
        prompt = (
            "You are a personal finance assistant. Using only these aggregates in COP cents, "
            f"write up to {MAX_ADVICE} concrete savings or budgeting tips in language "
            f"'{summary.locale}'. Do not invent figures.\n"
            'Answer with a JSON array like [{"title": "...", "detail": "..."}].\n'
            f"Data: {json.dumps(asdict(summary))}"
        )
        answer = self._model.generate_json(prompt)
        # Models sometimes wrap the list, as in {"tips": [...]}; the first list found is used.
        if isinstance(answer, dict):
            answer = next((value for value in answer.values() if isinstance(value, list)), None)
        if not isinstance(answer, list):
            return []
        return [
            Advice(item["title"][:MAX_FIELD_LENGTH], item["detail"][:MAX_FIELD_LENGTH])
            for item in answer[:MAX_ADVICE]
            if isinstance(item, dict)
            and isinstance(item.get("title"), str)
            and isinstance(item.get("detail"), str)
        ]
