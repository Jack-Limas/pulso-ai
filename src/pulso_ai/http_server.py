import hmac
import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import uvicorn

from pulso.ai.v1.analysis_engine_service_connect import AnalysisEngineServiceASGIApplication
from pulso_ai.analysis_engine import ConnectAnalysisEngine
from pulso_ai.config import Settings
from pulso_ai.engine import AnalysisEngine, build_engine

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

HEALTH_PATH = "/health"
API_KEY_HEADER = b"x-internal-key"
MAX_REQUEST_BYTES = 8 * 1024 * 1024


async def _send_json(send: Send, status: int, body: dict[str, str]) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": json.dumps(body).encode()})


def create_app(engine: AnalysisEngine, api_key: str):
    connect_app = AnalysisEngineServiceASGIApplication(
        ConnectAnalysisEngine(engine), read_max_bytes=MAX_REQUEST_BYTES
    )
    expected = api_key.encode()

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await connect_app(scope, receive, send)
            return
        if scope["path"] == HEALTH_PATH:
            await _send_json(send, 200, {"status": "ok"})
            return
        supplied = dict(scope["headers"]).get(API_KEY_HEADER, b"")
        if not hmac.compare_digest(supplied, expected):
            await _send_json(send, 401, {"code": "unauthenticated", "message": "Invalid key"})
            return
        await connect_app(scope, receive, send)

    return app


def main() -> None:
    settings = Settings()
    app = create_app(build_engine(settings), settings.internal_api_key)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
