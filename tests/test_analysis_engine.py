import threading
import time

import grpc
import pytest
import uvicorn
from grpc_health.v1 import health_pb2, health_pb2_grpc

from pulso.ai.v1 import analysis_engine_service_pb2 as pb
from pulso.ai.v1 import analysis_engine_service_pb2_grpc as pb_grpc
from pulso.ai.v1.analysis_engine_service_connect import AnalysisEngineServiceClientSync
from pulso_ai.advice import RuleAdvisor
from pulso_ai.categorization import Categorizer
from pulso_ai.engine import AnalysisEngine
from pulso_ai.http_server import create_app
from pulso_ai.server import create_server

API_KEY = "k" * 32
AUTH = (("x-internal-key", API_KEY),)
STAGES_PLUS_REPORT = 6


def engine() -> AnalysisEngine:
    return AnalysisEngine(Categorizer(None), RuleAdvisor())


def request() -> pb.AnalyzeStatementRequest:
    return pb.AnalyzeStatementRequest(
        entries=[
            pb.Entry(
                id="1",
                occurred_on="2026-10-05",
                description="STARBUCKS",
                merchant="STARBUCKS",
                type=pb.ENTRY_TYPE_EXPENSE,
                amount_cents=1_000_000,
            )
        ],
        current_balance_cents=5_000_000,
        locale="es",
    )


@pytest.fixture
def channel():
    server, port = create_server("127.0.0.1:0", engine(), API_KEY)
    server.start()
    with grpc.insecure_channel(f"127.0.0.1:{port}") as client_channel:
        yield client_channel
    server.stop(grace=None)


@pytest.fixture
def http_url(unused_tcp_port):
    config = uvicorn.Config(
        create_app(engine(), API_KEY), host="127.0.0.1", port=unused_tcp_port, log_level="error"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{unused_tcp_port}"
    server.should_exit = True
    thread.join(timeout=5)


def assert_stream(events: list[pb.AnalyzeStatementResponse]) -> None:
    assert len(events) == STAGES_PLUS_REPORT
    assert all(event.WhichOneof("event") == "stage" for event in events[:-1])
    report = events[-1].report
    assert report.categorized_entries[0].category_code == "food"
    assert report.forecast.projected_cents != 0


class TestNativeGrpc:
    def test_health_is_public(self, channel):
        response = health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest())

        assert response.status == health_pb2.HealthCheckResponse.SERVING

    def test_streams_every_stage_then_the_report(self, channel):
        stub = pb_grpc.AnalysisEngineServiceStub(channel)

        assert_stream(list(stub.AnalyzeStatement(request(), metadata=AUTH)))

    def test_rejects_a_missing_key(self, channel):
        stub = pb_grpc.AnalysisEngineServiceStub(channel)

        with pytest.raises(grpc.RpcError) as error:
            list(stub.AnalyzeStatement(request()))

        assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestConnectOverHttp1:
    def test_streams_every_stage_then_the_report(self, http_url):
        with AnalysisEngineServiceClientSync(http_url) as client:
            events = list(client.analyze_statement(request(), headers={"x-internal-key": API_KEY}))

        assert_stream(events)

    def test_rejects_a_wrong_key(self, http_url):
        with AnalysisEngineServiceClientSync(http_url) as client, pytest.raises(Exception):  # noqa: B017
            list(client.analyze_statement(request(), headers={"x-internal-key": "wrong"}))

    def test_health_needs_no_key(self, http_url):
        import httpx

        assert httpx.get(f"{http_url}/health").json() == {"status": "ok"}
