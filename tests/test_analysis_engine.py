import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from pulso.ai.v1 import analysis_engine_service_pb2 as pb
from pulso.ai.v1 import analysis_engine_service_pb2_grpc as pb_grpc
from pulso_ai.server import create_server


@pytest.fixture
def channel():
    server, port = create_server("127.0.0.1:0")
    server.start()
    with grpc.insecure_channel(f"127.0.0.1:{port}") as client_channel:
        yield client_channel
    server.stop(grace=None)


def test_health_reports_serving(channel):
    stub = health_pb2_grpc.HealthStub(channel)

    response = stub.Check(health_pb2.HealthCheckRequest(service=""))

    assert response.status == health_pb2.HealthCheckResponse.SERVING


def test_analysis_streams_every_stage_then_the_report(channel):
    stub = pb_grpc.AnalysisEngineServiceStub(channel)

    events = list(stub.AnalyzeStatement(pb.AnalyzeStatementRequest()))

    assert len(events) == 6
    assert all(event.WhichOneof("event") == "stage" for event in events[:-1])
    assert events[-1].WhichOneof("event") == "report"
