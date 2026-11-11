from collections import Counter, defaultdict
from statistics import fmean, median

import numpy as np
from sklearn.ensemble import IsolationForest

from pulso_ai.domain import Anomaly, CategorizedEntry, Entry, EntryKind

MIN_SAMPLES_FOR_OUTLIER = 5
MODIFIED_ZSCORE_THRESHOLD = 3.5
MODIFIED_ZSCORE_SCALE = 0.6745
MIN_RATIO_TO_MEDIAN = 2
DUPLICATE_WINDOW_DAYS = 2
MIN_HISTORY_FOR_NEW_FEE = 10
MIN_SAMPLES_FOR_FOREST = 30
FOREST_CONTAMINATION = 0.02
RANDOM_SEED = 42
FEE_KEYWORDS = ("COMISION", "CUOTA MANEJO", "SOBREGIRO", "FEE")

REASONS = {
    "es": {
        "high": "El valor supera considerablemente el promedio habitual de esta categoría ({avg}).",
        "duplicate": "Cobro repetido: mismo comercio y valor en menos de {days} días.",
        "fee": "Comisión que no aparece normalmente en tus movimientos.",
        "forest": "Combinación inusual de valor y frecuencia frente a tu historial.",
    },
    "en": {
        "high": "This amount is well above the usual average for this category ({avg}).",
        "duplicate": "Repeated charge: same merchant and amount within {days} days.",
        "fee": "A fee that does not normally appear in your activity.",
        "forest": "Unusual combination of amount and frequency compared to your history.",
    },
}


def _money(cents: float, locale: str) -> str:
    text = f"${cents / 100:,.0f}"
    return text.replace(",", ".") if locale == "es" else text


def detect_anomalies(
    entries: list[Entry], categorized: list[CategorizedEntry], locale: str
) -> list[Anomaly]:
    texts = REASONS.get(locale, REASONS["es"]) | {"locale": locale}
    category_of = {item.entry_id: item.category for item in categorized}
    expenses = [entry for entry in entries if entry.kind is EntryKind.EXPENSE]

    # Later detectors never overwrite an earlier one: the most explainable reason wins.
    found: dict[str, Anomaly] = {}
    for detector in (_high_amounts, _duplicates, _new_fees, _isolation_forest):
        for anomaly in detector(expenses, category_of, texts):
            found.setdefault(anomaly.entry_id, anomaly)
    return list(found.values())


def _high_amounts(
    expenses: list[Entry], category_of: dict[str, str], texts: dict[str, str]
) -> list[Anomaly]:
    by_category: dict[str, list[Entry]] = defaultdict(list)
    for entry in expenses:
        by_category[category_of.get(entry.id, "other")].append(entry)

    # Median based: in a small group, one huge charge inflates the mean and standard deviation
    # enough to hide itself, while the median and its deviation barely move.
    anomalies = []
    for group in by_category.values():
        if len(group) < MIN_SAMPLES_FOR_OUTLIER:
            continue
        amounts = [entry.amount_cents for entry in group]
        center = median(amounts)
        spread = median(abs(amount - center) for amount in amounts)
        total = sum(amounts)
        for entry in group:
            if entry.amount_cents < center * MIN_RATIO_TO_MEDIAN:
                continue
            score = (
                MODIFIED_ZSCORE_SCALE * (entry.amount_cents - center) / spread
                if spread
                else entry.amount_cents / center
            )
            if not spread or score >= MODIFIED_ZSCORE_THRESHOLD:
                others_average = (total - entry.amount_cents) / (len(group) - 1)
                reason = texts["high"].format(avg=_money(others_average, texts["locale"]))
                anomalies.append(Anomaly(entry.id, reason, round(score, 2)))
    return anomalies


def _duplicates(
    expenses: list[Entry], _category_of: dict[str, str], texts: dict[str, str]
) -> list[Anomaly]:
    last_seen: dict[tuple[str, int], Entry] = {}
    anomalies = []
    for entry in sorted(expenses, key=lambda item: item.occurred_on):
        key = (entry.merchant, entry.amount_cents)
        previous = last_seen.get(key)
        if previous and (entry.occurred_on - previous.occurred_on).days <= DUPLICATE_WINDOW_DAYS:
            reason = texts["duplicate"].format(days=DUPLICATE_WINDOW_DAYS + 1)
            anomalies.append(Anomaly(entry.id, reason, 1.0))
        last_seen[key] = entry
    return anomalies


def _new_fees(
    expenses: list[Entry], _category_of: dict[str, str], texts: dict[str, str]
) -> list[Anomaly]:
    if len(expenses) < MIN_HISTORY_FOR_NEW_FEE:
        return []
    occurrences = Counter(entry.merchant for entry in expenses)
    return [
        Anomaly(entry.id, texts["fee"], 1.0)
        for entry in expenses
        if occurrences[entry.merchant] == 1
        and any(keyword in entry.description.upper() for keyword in FEE_KEYWORDS)
    ]


def _isolation_forest(
    expenses: list[Entry], _category_of: dict[str, str], texts: dict[str, str]
) -> list[Anomaly]:
    if len(expenses) < MIN_SAMPLES_FOR_FOREST:
        return []
    frequency = Counter(entry.merchant for entry in expenses)
    features = np.array(
        [[np.log1p(entry.amount_cents), frequency[entry.merchant]] for entry in expenses]
    )
    forest = IsolationForest(contamination=FOREST_CONTAMINATION, random_state=RANDOM_SEED)
    labels = forest.fit_predict(features)
    scores = forest.decision_function(features)
    mean_amount = fmean(entry.amount_cents for entry in expenses)
    return [
        Anomaly(entry.id, texts["forest"], round(float(-score), 3))
        for entry, label, score in zip(expenses, labels, scores, strict=True)
        # Unusually small purchases are outliers too, but nobody needs an alert for them.
        if label == -1 and entry.amount_cents > mean_amount
    ]
