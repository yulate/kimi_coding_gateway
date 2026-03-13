from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.concurrency import ConcurrencyGate
from app.config import GatewayConfig
from app.debug_utils import DebugWriter
from app.metrics import RuntimeMetrics


@dataclass(frozen=True)
class GatewayRuntime:
    config: GatewayConfig
    normal_client: httpx.AsyncClient
    stream_client: httpx.AsyncClient
    debug_writer: DebugWriter
    normal_gate: ConcurrencyGate
    stream_gate: ConcurrencyGate
    metrics: RuntimeMetrics


def build_timeout(config: GatewayConfig) -> httpx.Timeout:
    return httpx.Timeout(
        connect=config.connect_timeout_seconds,
        write=config.write_timeout_seconds,
        read=config.read_timeout_seconds,
        pool=config.pool_timeout_seconds,
    )


def build_limits(max_connections: int, max_keepalive_connections: int, keepalive_expiry: float):
    return httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
        keepalive_expiry=keepalive_expiry,
    )


def build_client(
    config: GatewayConfig,
    max_connections: int,
    max_keepalive_connections: int,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=build_timeout(config),
        limits=build_limits(
            max_connections,
            max_keepalive_connections,
            config.keepalive_expiry_seconds,
        ),
        http2=False,
    )


def create_runtime(config: GatewayConfig) -> GatewayRuntime:
    return GatewayRuntime(
        config=config,
        normal_client=build_client(
            config,
            config.non_stream_max_connections,
            config.non_stream_max_keepalive_connections,
        ),
        stream_client=build_client(
            config,
            config.stream_max_connections,
            config.stream_max_keepalive_connections,
        ),
        debug_writer=DebugWriter(config.debug_mode, config.debug_jsonl_file),
        normal_gate=ConcurrencyGate(
            "normal",
            config.non_stream_max_upstream_concurrency,
            config.non_stream_max_queue_size,
            config.upstream_queue_timeout_seconds,
        ),
        stream_gate=ConcurrencyGate(
            "stream",
            config.stream_max_upstream_concurrency,
            config.stream_max_queue_size,
            config.upstream_queue_timeout_seconds,
        ),
        metrics=RuntimeMetrics(),
    )


async def close_runtime(runtime: GatewayRuntime):
    await runtime.normal_client.aclose()
    await runtime.stream_client.aclose()
