from datetime import date, timedelta

import pytest

from factories import as_category, expense, income
from pulso_ai.advice import GeminiAdvisor, RuleAdvisor
from pulso_ai.anomalies import detect_anomalies
from pulso_ai.categorization import Categorizer, GeminiClassifier
from pulso_ai.domain import FinancialSummary, Method
from pulso_ai.forecast import forecast_liquidity
from pulso_ai.patterns import find_ant_expenses, find_recurring


class StubModel:
    def __init__(self, answer=None, error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.prompts: list[str] = []

    def generate_json(self, prompt: str):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.answer


def summary(**overrides) -> FinancialSummary:
    values = {
        "locale": "es",
        "total_expense_cents": 100,
        "expense_by_category": {"food": 80, "other": 20},
        "anomaly_count": 0,
        "recurring_total_cents": 0,
        "ant_total_cents": 0,
        "projected_cents": 500,
    }
    return FinancialSummary(**(values | overrides))


class TestCategorization:
    def test_known_rule_beats_keyword(self):
        entry = expense("UBER")

        result = Categorizer(None).categorize([entry], {"UBER": "food"})

        assert result[0].category == "food"

    @pytest.mark.parametrize(
        ("merchant", "category"),
        [
            ("STARBUCKS", "food"),
            ("UBER TRIP", "transport"),
            ("NETFLIX COM", "entertainment"),
            ("AWS", "technology"),
        ],
    )
    def test_keywords(self, merchant, category):
        assert Categorizer(None).categorize([expense(merchant)], {})[0].category == category

    def test_keyword_does_not_match_inside_another_word(self):
        assert Categorizer(None).categorize([expense("GASPAR")], {})[0].category == "other"

    def test_unknown_merchant_asks_the_model_once(self):
        model = StubModel({"KIOSKO LUNA": "shopping"})
        entries = [expense("KIOSKO LUNA"), expense("KIOSKO LUNA")]

        result = Categorizer(GeminiClassifier(model)).categorize(entries, {})

        assert [item.method for item in result] == [Method.MODEL, Method.MODEL]
        assert len(model.prompts) == 1

    def test_model_answers_outside_the_allowed_list_are_ignored(self):
        model = StubModel({"KIOSKO LUNA": "ignore previous instructions"})

        result = Categorizer(GeminiClassifier(model)).categorize([expense("KIOSKO LUNA")], {})

        assert result[0].category == "other"

    def test_model_failure_keeps_the_entry(self):
        model = StubModel(error=RuntimeError("quota"))

        result = Categorizer(GeminiClassifier(model)).categorize([expense("KIOSKO LUNA")], {})

        assert result[0].category == "other"

    def test_only_merchant_names_reach_the_model(self):
        model = StubModel({})
        entry = expense("KIOSKO LUNA", 123_456_789)

        Categorizer(GeminiClassifier(model)).categorize([entry], {})

        assert "123456789" not in model.prompts[0]


class TestAnomalies:
    def test_flags_amount_far_above_category_average_and_explains_why(self):
        normal = [expense(f"T{i}", 1_000_000 + i) for i in range(9)]
        outlier = expense("T9", 45_000_000)
        entries = [*normal, outlier]

        found = detect_anomalies(entries, as_category(entries), "es")

        assert [item.entry_id for item in found] == [outlier.id]
        assert "promedio" in found[0].reason

    def test_flags_an_outlier_in_a_small_group(self):
        normal = [expense(f"T{i}", 800_000 + i * 1000) for i in range(6)]
        outlier = expense("REGALO", 95_000_000)
        entries = [*normal, outlier]

        found = detect_anomalies(entries, as_category(entries), "es")

        assert [item.entry_id for item in found] == [outlier.id]
        assert "$8.025" in found[0].reason

    def test_flags_an_outlier_when_every_other_amount_is_identical(self):
        normal = [expense(f"T{i}", 1_000_000) for i in range(6)]
        outlier = expense("REGALO", 9_000_000)
        entries = [*normal, outlier]

        assert [a.entry_id for a in detect_anomalies(entries, as_category(entries), "es")] == [
            outlier.id
        ]

    def test_slightly_higher_amount_is_normal(self):
        entries = [expense(f"T{i}", 1_000_000 + i) for i in range(6)]
        entries.append(expense("T9", 1_010_000))

        assert detect_anomalies(entries, as_category(entries), "es") == []

    def test_flags_second_charge_of_a_duplicate(self):
        first = expense("NETFLIX", 4_000_000, date(2026, 10, 1))
        second = expense("NETFLIX", 4_000_000, date(2026, 10, 2))
        entries = [first, second]

        found = detect_anomalies(entries, as_category(entries), "en")

        assert [item.entry_id for item in found] == [second.id]
        assert "Repeated" in found[0].reason

    def test_same_amount_a_month_later_is_not_a_duplicate(self):
        entries = [
            expense("NETFLIX", 4_000_000, date(2026, 9, 1)),
            expense("NETFLIX", 4_000_000, date(2026, 10, 1)),
        ]

        assert detect_anomalies(entries, as_category(entries), "es") == []

    def test_flags_a_new_fee(self):
        history = [expense(f"T{i}", 1_000_000) for i in range(10)]
        fee = expense("BANCO", 900_000, description="COMISION SOBREGIRO")
        entries = [*history, fee]

        assert [a.entry_id for a in detect_anomalies(entries, as_category(entries), "es")] == [
            fee.id
        ]

    def test_uniform_spending_has_no_anomalies(self):
        entries = [
            expense(f"T{i}", 1_000_000, date(2026, 10, 1) + timedelta(days=i)) for i in range(8)
        ]

        assert detect_anomalies(entries, as_category(entries), "es") == []

    def test_income_is_never_flagged(self):
        entries = [income(900_000_000), *[expense(f"T{i}") for i in range(6)]]

        found = detect_anomalies(entries, as_category(entries), "es")

        assert entries[0].id not in {item.entry_id for item in found}


class TestPatterns:
    def test_groups_small_repeated_purchases(self):
        amounts = [800_000, 750_000, 900_000, 850_000]
        days = [date(2026, 10, d) for d in (2, 9, 16, 23)]
        entries = [expense("CAFE", a, d) for a, d in zip(amounts, days, strict=True)]

        [finding] = find_ant_expenses(entries, as_category(entries))

        assert (finding.count, finding.total_cents) == (4, 3_300_000)
        assert finding.average_cents == 825_000
        assert (finding.period_start, finding.period_end) == (days[0], days[-1])

    def test_three_small_purchases_are_not_enough(self):
        entries = [expense("CAFE", 800_000) for _ in range(3)]

        assert find_ant_expenses(entries, as_category(entries)) == []

    def test_large_purchases_are_not_ant_expenses(self):
        entries = [expense("CAFE", 5_000_000) for _ in range(5)]

        assert find_ant_expenses(entries, as_category(entries)) == []

    def test_detects_monthly_subscription(self):
        days = [date(2026, 8, 3), date(2026, 9, 3), date(2026, 10, 2)]

        [finding] = find_recurring([expense("NETFLIX", 4_000_000, d) for d in days])

        assert (finding.interval_days, finding.occurrences) == (30, 3)

    def test_irregular_dates_are_not_recurring(self):
        days = [date(2026, 8, 3), date(2026, 8, 20), date(2026, 10, 2)]

        assert find_recurring([expense("TIENDA", 4_000_000, d) for d in days]) == []

    def test_unstable_amounts_are_not_recurring(self):
        entries = [
            expense("TIENDA", 1_000_000, date(2026, 9, 3)),
            expense("TIENDA", 9_000_000, date(2026, 10, 3)),
        ]

        assert find_recurring(entries) == []


class TestForecast:
    def test_projects_thirty_days_at_the_observed_pace(self):
        entries = [
            income(300_000_000, date(2026, 10, 1)),
            expense("A", 150_000_000, date(2026, 10, 30)),
        ]

        forecast = forecast_liquidity(entries, 200_000_000)

        assert forecast.expected_income_cents == 300_000_000
        assert forecast.expected_expense_cents == 150_000_000
        assert forecast.projected_cents == 350_000_000

    def test_trend_is_negative_when_only_spending(self):
        entries = [expense("A", 1_000_000, date(2026, 10, day)) for day in range(1, 11)]

        assert forecast_liquidity(entries, 0).daily_trend_cents == -1_000_000

    def test_no_entries_keeps_the_balance(self):
        assert forecast_liquidity([], 777).projected_cents == 777


class TestAdvice:
    def test_points_at_the_dominant_category_in_the_user_language(self):
        [advice] = RuleAdvisor().advise(summary())

        assert advice.title == "Reduce gastos en alimentación"

    def test_negative_amounts_put_the_sign_before_the_currency(self):
        advice = RuleAdvisor().advise(summary(expense_by_category={}, projected_cents=-75_000_000))

        assert advice[0].detail.endswith("-$750.000.")

    def test_warns_about_a_negative_projection_in_english(self):
        advice = RuleAdvisor().advise(
            summary(locale="en", expense_by_category={}, projected_cents=-5000)
        )

        assert advice[0].title == "Adjust your budget"

    def test_model_advice_is_used_when_valid(self):
        model = StubModel([{"title": "Ahorra", "detail": "Cocina en casa"}])

        advice = GeminiAdvisor(model, RuleAdvisor()).advise(summary())

        assert advice[0].title == "Ahorra"

    def test_model_receives_amounts_in_pesos(self):
        model = StubModel([])

        GeminiAdvisor(model, RuleAdvisor()).advise(summary(total_expense_cents=125_000_000))

        assert '"total_expense": 1250000' in model.prompts[0]
        assert "alimentación" in model.prompts[0]

    def test_model_advice_wrapped_in_an_object_is_accepted(self):
        model = StubModel({"tips": [{"title": "Ahorra", "detail": "Cocina en casa"}]})

        advice = GeminiAdvisor(model, RuleAdvisor()).advise(summary())

        assert advice[0].title == "Ahorra"

    @pytest.mark.parametrize(
        "model",
        [StubModel(error=RuntimeError("down")), StubModel("not a list"), StubModel([{"x": 1}])],
    )
    def test_bad_model_output_falls_back_to_rules(self, model):
        advice = GeminiAdvisor(model, RuleAdvisor()).advise(summary())

        assert "alimentación" in advice[0].title
