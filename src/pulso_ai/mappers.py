from datetime import date

from pulso.ai.v1 import analysis_engine_service_pb2 as pb
from pulso_ai.domain import AnalysisInput, Entry, EntryKind, Method, Report, Stage

_STAGES = {
    Stage.CATEGORIZING: pb.ANALYSIS_STAGE_CATEGORIZING,
    Stage.DETECTING_ANOMALIES: pb.ANALYSIS_STAGE_DETECTING_ANOMALIES,
    Stage.FINDING_PATTERNS: pb.ANALYSIS_STAGE_FINDING_PATTERNS,
    Stage.FORECASTING: pb.ANALYSIS_STAGE_FORECASTING,
    Stage.RECOMMENDING: pb.ANALYSIS_STAGE_RECOMMENDING,
}
_METHODS = {
    Method.RULE: pb.CATEGORIZATION_METHOD_RULE,
    Method.MODEL: pb.CATEGORIZATION_METHOD_MODEL,
}


def to_input(request: pb.AnalyzeStatementRequest) -> AnalysisInput:
    return AnalysisInput(
        entries=[
            Entry(
                id=entry.id,
                occurred_on=date.fromisoformat(entry.occurred_on),
                description=entry.description,
                merchant=entry.merchant,
                kind=(
                    EntryKind.INCOME
                    if entry.type == pb.ENTRY_TYPE_INCOME
                    else EntryKind.EXPENSE
                ),
                amount_cents=entry.amount_cents,
            )
            for entry in request.entries
        ],
        current_balance_cents=request.current_balance_cents,
        locale=request.locale,
        known_categories=dict(request.known_categories),
    )


def to_response(event: Stage | Report) -> pb.AnalyzeStatementResponse:
    if isinstance(event, Stage):
        return pb.AnalyzeStatementResponse(stage=_STAGES[event])
    return pb.AnalyzeStatementResponse(report=_to_report(event))


def _to_report(report: Report) -> pb.AnalysisReport:
    return pb.AnalysisReport(
        categorized_entries=[
            pb.CategorizedEntry(
                entry_id=item.entry_id,
                merchant=item.merchant,
                category_code=item.category,
                method=_METHODS[item.method],
            )
            for item in report.categorized
        ],
        anomalies=[
            pb.AnomalyFinding(entry_id=item.entry_id, reason=item.reason, score=item.score)
            for item in report.anomalies
        ],
        recurring=[
            pb.RecurringFinding(
                merchant=item.merchant,
                average_cents=item.average_cents,
                interval_days=item.interval_days,
                occurrences=item.occurrences,
            )
            for item in report.recurring
        ],
        ant_expenses=[
            pb.AntExpenseFinding(
                merchant=item.merchant,
                category_code=item.category,
                count=item.count,
                total_cents=item.total_cents,
                average_cents=item.average_cents,
                period_start=item.period_start.isoformat(),
                period_end=item.period_end.isoformat(),
            )
            for item in report.ant_expenses
        ],
        forecast=pb.Forecast(
            expected_income_cents=report.forecast.expected_income_cents,
            expected_expense_cents=report.forecast.expected_expense_cents,
            projected_cents=report.forecast.projected_cents,
            daily_trend_cents=report.forecast.daily_trend_cents,
        ),
        advice=[pb.Advice(title=item.title, detail=item.detail) for item in report.advice],
    )
