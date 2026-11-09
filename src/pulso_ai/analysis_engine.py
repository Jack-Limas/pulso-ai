import asyncio
from collections.abc import AsyncIterator, Iterator

from pulso.ai.v1 import analysis_engine_service_pb2 as pb
from pulso.ai.v1 import analysis_engine_service_pb2_grpc as pb_grpc
from pulso_ai.engine import AnalysisEngine
from pulso_ai.mappers import to_input, to_response


class AnalysisEngineServicer(pb_grpc.AnalysisEngineServiceServicer):
    """Native gRPC adapter over HTTP/2."""

    def __init__(self, engine: AnalysisEngine) -> None:
        self._engine = engine

    def AnalyzeStatement(  # noqa: N802
        self, request: pb.AnalyzeStatementRequest, context: object
    ) -> Iterator[pb.AnalyzeStatementResponse]:
        for event in self._engine.run(to_input(request)):
            yield to_response(event)


class ConnectAnalysisEngine:
    """Connect adapter over HTTP/1.1, for hosts whose proxy cannot carry native gRPC."""

    def __init__(self, engine: AnalysisEngine) -> None:
        self._engine = engine

    async def analyze_statement(
        self, request: pb.AnalyzeStatementRequest, ctx: object
    ) -> AsyncIterator[pb.AnalyzeStatementResponse]:
        events = self._engine.run(to_input(request))
        # Analysis is CPU bound and may call the model, so it must not block the event loop.
        while (event := await asyncio.to_thread(next, events, None)) is not None:
            yield to_response(event)
