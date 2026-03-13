from __future__ import annotations

from dataclasses import dataclass

import httpx

REQUEST_DEADLINE_MESSAGE = "Request exceeded total gateway deadline."


@dataclass(frozen=True)
class GatewayError(Exception):
    status_code: int
    error_type: str
    message: str


def build_request_deadline_error() -> GatewayError:
    return GatewayError(
        504,
        "gateway_request_deadline_exceeded",
        REQUEST_DEADLINE_MESSAGE,
    )


def map_upstream_error(exc: Exception) -> GatewayError:
    if isinstance(exc, httpx.ReadTimeout):
        return GatewayError(504, "upstream_read_timeout", str(exc))
    if isinstance(exc, httpx.WriteTimeout):
        return GatewayError(504, "upstream_write_timeout", str(exc))
    if isinstance(exc, httpx.ConnectTimeout):
        return GatewayError(504, "upstream_connect_timeout", str(exc))
    if isinstance(exc, httpx.PoolTimeout):
        return GatewayError(503, "upstream_pool_timeout", str(exc))
    if isinstance(exc, httpx.ConnectError):
        return GatewayError(503, "upstream_connect_error", str(exc))
    if isinstance(exc, httpx.RemoteProtocolError):
        return GatewayError(502, "upstream_protocol_error", str(exc))
    if isinstance(exc, httpx.HTTPError):
        return GatewayError(502, "upstream_http_error", str(exc))
    return GatewayError(500, "gateway_internal_error", str(exc))


def normalize_gateway_exception(exc: Exception) -> GatewayError:
    if isinstance(exc, GatewayError):
        return exc
    if isinstance(exc, TimeoutError):
        return build_request_deadline_error()
    return map_upstream_error(exc)
