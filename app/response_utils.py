from __future__ import annotations

import json

import httpx
from fastapi.responses import JSONResponse, StreamingResponse

from app.debug_utils import parse_json_payload
from app.errors import GatewayError

REQUEST_ID_HEADER = "X-Gateway-Request-Id"
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def build_error_payload(error: GatewayError, request_id: str) -> dict:
    return {
        "error": {
            "message": error.message,
            "type": error.error_type,
            "request_id": request_id,
        }
    }


def build_json_error_response(error: GatewayError, request_id: str) -> JSONResponse:
    return JSONResponse(
        content=build_error_payload(error, request_id),
        status_code=error.status_code,
        headers={REQUEST_ID_HEADER: request_id},
    )


def build_stream_error_response(error: GatewayError, request_id: str):
    payload = build_error_payload(error, request_id)

    async def event_stream():
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        status_code=error.status_code,
        headers={REQUEST_ID_HEADER: request_id},
    )


def build_upstream_status_error(status_code: int, response_body: bytes) -> GatewayError:
    details = parse_json_payload(response_body)
    message = f"Upstream returned status {status_code}"
    if isinstance(details, dict) and "error" in details:
        message = f"{message}: {details['error']}"
    return GatewayError(status_code, "upstream_status_error", message)


def filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        result[key] = value
    return result
