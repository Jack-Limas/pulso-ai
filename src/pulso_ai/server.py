import hmac
import logging
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from pulso.ai.v1 import analysis_engine_service_pb2_grpc as pb_grpc
from pulso_ai.analysis_engine import AnalysisEngineServicer
from pulso_ai.config import Settings
from pulso_ai.engine import AnalysisEngine, build_engine

MAX_WORKERS = 10
SERVICE_NAME = "pulso.ai.v1.AnalysisEngineService"
API_KEY_HEADER = "x-internal-key"
PUBLIC_METHOD_PREFIX = "/grpc.health.v1.Health/"


class ApiKeyInterceptor(grpc.ServerInterceptor):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def intercept_service(self, continuation, handler_call_details):
        if handler_call_details.method.startswith(PUBLIC_METHOD_PREFIX):
            return continuation(handler_call_details)
        supplied = dict(handler_call_details.invocation_metadata).get(API_KEY_HEADER, "")
        if hmac.compare_digest(supplied, self._api_key):
            return continuation(handler_call_details)

        def reject(_request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid internal key")

        return grpc.unary_stream_rpc_method_handler(reject)


def create_server(address: str, engine: AnalysisEngine, api_key: str) -> tuple[grpc.Server, int]:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=MAX_WORKERS),
        interceptors=[ApiKeyInterceptor(api_key)],
    )
    pb_grpc.add_AnalysisEngineServiceServicer_to_server(AnalysisEngineServicer(engine), server)

    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set(SERVICE_NAME, health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    port = server.add_insecure_port(address)
    return server, port


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    server, port = create_server(
        f"0.0.0.0:{settings.port}", build_engine(settings), settings.internal_api_key
    )
    server.start()
    logging.info("Native gRPC server listening on port %s", port)
    server.wait_for_termination()


if __name__ == "__main__":
    main()
