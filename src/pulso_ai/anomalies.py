from collections import Counter, defaultdict
from statistics import fmean, median

import numpy as np
from sklearn.ensemble import IsolationForest

from pulso_ai.domain import Anomaly, CategorizedEntry, Entry, EntryKind

MIN_SAMPLES_FOR_OUTLIER = 5
MODIFIED_ZSCORE_THRESHOLD = 3.5
MODIFIED_ZSCORE_SCALE = 0.6745
MIN_RATIO_TO_MEDIAN = 2
MIN_MERCHANT_HISTORY = 2
# Large and expected: a rent or a tuition is not unusual just because it is the biggest charge.
FIXED_COST_CATEGORIES = frozenset({"housing", "utilities", "education", "health"})
# Scheduled payments are large by nature; without history they look like outliers but are not.
SCHEDULED_PAYMENT_WORDS = frozenset(
    {"NOMINA", "CUOTA", "CREDITO", "HIPOTECA", "ARRIENDO", "SEGURO", "PENSION", "SOAT",
     "SUSCRIPCION", "SUBSCRIPTION", "MEMBRESIA", "PLAN", "CLOUD", "SERVICES", "POLIZA"}
)
FREQUENT_WINDOW_DAYS = 30
FREQUENT_MIN_CHARGES = 4
DUPLICATE_WINDOW_DAYS = 2
MIN_HISTORY_FOR_NEW_FEE = 10
MIN_SAMPLES_FOR_FOREST = 30
FOREST_CONTAMINATION = 0.02
RANDOM_SEED = 42
FEE_KEYWORDS = ("COMISION", "CUOTA MANEJO", "SOBREGIRO", "FEE")

REASONS = {
    "es": {
        "high": "El valor supera considerablemente el promedio habitual de esta categoría ({avg}).",
        "high_overall": "El valor supera considerablemente tu gasto habitual ({avg}).",
        "duplicate": "Cobro repetido: mismo comercio y valor en menos de {days} días.",
        "fee": "Comisión que no aparece normalmente en tus movimientos.",
        "forest": "Combinación inusual de valor y frecuencia frente a tu historial.",
    },
    "en": {
        "high": "This amount is well above the usual average for this category ({avg}).",
        "high_overall": "This amount is well above your usual spending ({avg}).",
        "duplicate": "Repeated charge: same merchant and amount within {days} days.",
        "fee": "A fee that does not normally appear in your activity.",
        "forest": "Unusual combination of amount and frequency compared to your history.",
    },
}


def _money(cents: float, locale: str) -> str:
    text = f"{'-' if cents < 0 else ''}${abs(cents) / 100:,.0f}"
    return text.replace(",", ".") if locale == "es" else text


def detect_anomalies(
    entries: list[Entry], categorized: list[CategorizedEntry], locale: str
) -> list[Anomaly]:
    texts = REASONS.get(locale, REASONS["es"]) | {"locale": locale}
    category_of = {item.entry_id: item.category for item in categorized}
    expenses = [entry for entry in entries if entry.kind is EntryKind.EXPENSE]

    # Amount detectors skip what is expected: a merchant's usual price or a scheduled payment.
    expected = _habitual_ids(expenses) | {entry.id for entry in expenses if _is_scheduled(entry)}
    # Later detectors never overwrite an earlier one: the most explainable reason wins.
    found: dict[str, Anomaly] = {}
    for detector in (_high_amounts, _duplicates, _new_fees, _isolation_forest):
        judges_amount = detector in (_high_amounts, _isolation_forest)
        for anomaly in detector(expenses, category_of, texts):
            if judges_amount and anomaly.entry_id in expected:
                continue
            found.setdefault(anomaly.entry_id, anomaly)
    return list(found.values())


def _habitual_ids(expenses: list[Entry]) -> set[str]:
    """A charge is habitual when it is in line with what this merchant usually costs.

    Categories mix very different merchants (a coffee and a food delivery are both "food"),
    so a merchant with its own history is judged against itself first.
    """
    by_merchant: dict[str, list[Entry]] = defaultdict(list)
    for entry in expenses:
        by_merchant[entry.merchant].append(entry)
    habitual = set()
    for group in by_merchant.values():
        if len(group) < MIN_MERCHANT_HISTORY:
            continue
        usual = median(entry.amount_cents for entry in group)
        habitual.update(
            entry.id for entry in group if entry.amount_cents < usual * MIN_RATIO_TO_MEDIAN
        )
    return habitual


def _outliers(
    candidates: list[Entry], pool: list[Entry], reason_key: str, texts: dict[str, str]
) -> list[Anomaly]:
    """Median based: one huge charge inflates a mean enough to hide itself.

    A median barely moves, so the charge still stands out.
    """
    amounts = [entry.amount_cents for entry in pool]
    center = median(amounts)
    spread = median(abs(amount - center) for amount in amounts)
    total = sum(amounts)
    anomalies = []
    for entry in candidates:
        if entry.amount_cents < center * MIN_RATIO_TO_MEDIAN:
            continue
        score = (
            MODIFIED_ZSCORE_SCALE * (entry.amount_cents - center) / spread
            if spread
            else entry.amount_cents / center
        )
        if not spread or score >= MODIFIED_ZSCORE_THRESHOLD:
            others_average = (total - entry.amount_cents) / (len(pool) - 1)
            reason = texts[reason_key].format(avg=_money(others_average, texts["locale"]))
            anomalies.append(Anomaly(entry.id, reason, round(score, 2)))
    return anomalies


def _is_scheduled(entry: Entry) -> bool:
    return not SCHEDULED_PAYMENT_WORDS.isdisjoint(entry.description.upper().split())


def _high_amounts(
    expenses: list[Entry], category_of: dict[str, str], texts: dict[str, str]
) -> list[Anomaly]:
    by_category: dict[str, list[Entry]] = defaultdict(list)
    for entry in expenses:
        by_category[category_of.get(entry.id, "other")].append(entry)

    anomalies = []
    sparse: list[Entry] = []
    for category, group in by_category.items():
        if len(group) >= MIN_SAMPLES_FOR_OUTLIER:
            anomalies.extend(_outliers(group, group, "high", texts))
        elif category not in FIXED_COST_CATEGORIES:
            sparse.extend(group)
    # A category with a single big purchase has nothing to compare against, so it is judged
    # against all spending instead; otherwise a new user's largest charge could never stand out.
    if sparse and len(expenses) >= MIN_SAMPLES_FOR_OUTLIER:
        anomalies.extend(_outliers(sparse, expenses, "high_overall", texts))
    return anomalies


def _duplicates(
    expenses: list[Entry], _category_of: dict[str, str], texts: dict[str, str]
) -> list[Anomaly]:
    dates_by_merchant: dict[str, list] = defaultdict(list)
    for entry in expenses:
        dates_by_merchant[entry.merchant].append(entry.occurred_on)

    def is_frequent(entry: Entry) -> bool:
        # Tolls or coffees repeat by habit: the same amount twice is not a double charge there.
        nearby = [
            day
            for day in dates_by_merchant[entry.merchant]
            if abs((entry.occurred_on - day).days) <= FREQUENT_WINDOW_DAYS
        ]
        return len(nearby) >= FREQUENT_MIN_CHARGES

    last_seen: dict[tuple[str, int], Entry] = {}
    anomalies = []
    for entry in sorted(expenses, key=lambda item: item.occurred_on):
        key = (entry.merchant, entry.amount_cents)
        previous = last_seen.get(key)
        if (
            previous
            and (entry.occurred_on - previous.occurred_on).days <= DUPLICATE_WINDOW_DAYS
            and not is_frequent(entry)
        ):
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
