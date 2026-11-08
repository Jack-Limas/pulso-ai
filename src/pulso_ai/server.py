import logging
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from pulso.ai.v1 import analysis_engine_service_pb2_grpc as pb_grpc
from pulso_ai.analysis_engine import AnalysisEngineServicer
from pulso_ai.config import Settings

MAX_WORKERS = 10
SERVICE_NAME = "pulso.ai.v1.AnalysisEngineService"


def create_server(address: str) -> tuple[grpc.Server, int]:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    pb_grpc.add_AnalysisEngineServiceServicer_to_server(AnalysisEngineServicer(), server)

    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set(SERVICE_NAME, health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    port = server.add_insecure_port(address)
    return server, port


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    server, port = create_server(f"0.0.0.0:{settings.port}")
    server.start()
    logging.info("gRPC server listening on port %s", port)
    server.wait_for_termination()


if __name__ == "__main__":
    main()
