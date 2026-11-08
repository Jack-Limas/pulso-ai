from collections.abc import Iterator

from pulso.ai.v1 import analysis_engine_service_pb2 as pb
from pulso.ai.v1 import analysis_engine_service_pb2_grpc as pb_grpc

STAGES = (
    pb.ANALYSIS_STAGE_CATEGORIZING,
    pb.ANALYSIS_STAGE_DETECTING_ANOMALIES,
    pb.ANALYSIS_STAGE_FINDING_PATTERNS,
    pb.ANALYSIS_STAGE_FORECASTING,
    pb.ANALYSIS_STAGE_RECOMMENDING,
)


class AnalysisEngineServicer(pb_grpc.AnalysisEngineServiceServicer):
    def AnalyzeStatement(  # noqa: N802
        self, request: pb.AnalyzeStatementRequest, context: object
    ) -> Iterator[pb.AnalyzeStatementResponse]:
        for stage in STAGES:
            yield pb.AnalyzeStatementResponse(stage=stage)
        yield pb.AnalyzeStatementResponse(report=pb.AnalysisReport())
