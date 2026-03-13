from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_KIMI_BASE_URL = "https://api.kimi.com/coding/v1"
DEFAULT_KIMI_API_KEY = "sk-kimi"
DEFAULT_USER_AGENT = "KimiCLI/1.3"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MAX_UPSTREAM_CONCURRENCY = 10
DEFAULT_QUEUE_TIMEOUT_SECONDS = 10.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_WRITE_TIMEOUT_SECONDS = 30.0
DEFAULT_READ_TIMEOUT_SECONDS = 300.0
DEFAULT_POOL_TIMEOUT_SECONDS = 5.0
DEFAULT_KEEPALIVE_EXPIRY_SECONDS = 30.0
DEFAULT_REQUEST_DEADLINE_SECONDS = 600.0
DEFAULT_DISCONNECT_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_QUEUE_MULTIPLIER = 2


@dataclass(frozen=True)
class GatewayConfig:
    kimi_base_url: str
    kimi_api_key: str
    kimi_cli_user_agent: str
    gateway_host: str
    gateway_port: int
    debug_mode: bool
    debug_jsonl_file: str
    default_reasoning_effort: str
    max_upstream_concurrency: int
    non_stream_max_upstream_concurrency: int
    stream_max_upstream_concurrency: int
    non_stream_max_queue_size: int
    stream_max_queue_size: int
    upstream_queue_timeout_seconds: float
    request_deadline_seconds: float
    disconnect_poll_interval_seconds: float
    connect_timeout_seconds: float
    write_timeout_seconds: float
    read_timeout_seconds: float
    pool_timeout_seconds: float
    non_stream_max_connections: int
    stream_max_connections: int
    non_stream_max_keepalive_connections: int
    stream_max_keepalive_connections: int
    keepalive_expiry_seconds: float


def get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() == "true"


def get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def get_env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None:
        return None
    return int(value)


def split_concurrency(total: int) -> tuple[int, int]:
    stream = max(1, total // 3)
    normal = max(1, total - stream)
    return normal, stream


def resolve_pool_size(name: str, fallback: int, legacy_value: int | None) -> int:
    return get_env_int(name, legacy_value or fallback)


def load_config() -> GatewayConfig:
    max_upstream_concurrency = get_env_int(
        "GATEWAY_MAX_UPSTREAM_CONCURRENCY",
        DEFAULT_MAX_UPSTREAM_CONCURRENCY,
    )
    normal_concurrency, stream_concurrency = split_concurrency(max_upstream_concurrency)
    normal_concurrency = get_env_int(
        "GATEWAY_NON_STREAM_MAX_UPSTREAM_CONCURRENCY",
        normal_concurrency,
    )
    stream_concurrency = get_env_int(
        "GATEWAY_STREAM_MAX_UPSTREAM_CONCURRENCY",
        stream_concurrency,
    )
    legacy_max_connections = get_env_optional_int("GATEWAY_MAX_CONNECTIONS")
    legacy_keepalive = get_env_optional_int("GATEWAY_MAX_KEEPALIVE_CONNECTIONS")
    return GatewayConfig(
        kimi_base_url=os.getenv("KIMI_BASE_URL", DEFAULT_KIMI_BASE_URL),
        kimi_api_key=os.getenv("KIMI_API_KEY") or DEFAULT_KIMI_API_KEY,
        kimi_cli_user_agent=os.getenv("KIMI_CLI_USER_AGENT", DEFAULT_USER_AGENT),
        gateway_host=os.getenv("GATEWAY_HOST", DEFAULT_HOST),
        gateway_port=get_env_int("GATEWAY_PORT", DEFAULT_PORT),
        debug_mode=get_env_bool("GATEWAY_DEBUG", False),
        debug_jsonl_file=os.getenv("GATEWAY_DEBUG_JSONL_FILE", "gateway_requests.jsonl"),
        default_reasoning_effort=os.getenv("GATEWAY_REASONING_EFFORT", DEFAULT_REASONING_EFFORT),
        max_upstream_concurrency=max_upstream_concurrency,
        non_stream_max_upstream_concurrency=normal_concurrency,
        stream_max_upstream_concurrency=stream_concurrency,
        non_stream_max_queue_size=get_env_int(
            "GATEWAY_NON_STREAM_MAX_QUEUE_SIZE",
            normal_concurrency * DEFAULT_QUEUE_MULTIPLIER,
        ),
        stream_max_queue_size=get_env_int(
            "GATEWAY_STREAM_MAX_QUEUE_SIZE",
            stream_concurrency * DEFAULT_QUEUE_MULTIPLIER,
        ),
        upstream_queue_timeout_seconds=get_env_float(
            "GATEWAY_UPSTREAM_QUEUE_TIMEOUT_SECONDS",
            DEFAULT_QUEUE_TIMEOUT_SECONDS,
        ),
        request_deadline_seconds=get_env_float(
            "GATEWAY_REQUEST_DEADLINE_SECONDS",
            DEFAULT_REQUEST_DEADLINE_SECONDS,
        ),
        disconnect_poll_interval_seconds=get_env_float(
            "GATEWAY_DISCONNECT_POLL_INTERVAL_SECONDS",
            DEFAULT_DISCONNECT_POLL_INTERVAL_SECONDS,
        ),
        connect_timeout_seconds=get_env_float("GATEWAY_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT_SECONDS),
        write_timeout_seconds=get_env_float("GATEWAY_WRITE_TIMEOUT_SECONDS", DEFAULT_WRITE_TIMEOUT_SECONDS),
        read_timeout_seconds=get_env_float("GATEWAY_READ_TIMEOUT_SECONDS", DEFAULT_READ_TIMEOUT_SECONDS),
        pool_timeout_seconds=get_env_float("GATEWAY_POOL_TIMEOUT_SECONDS", DEFAULT_POOL_TIMEOUT_SECONDS),
        non_stream_max_connections=resolve_pool_size(
            "GATEWAY_NON_STREAM_MAX_CONNECTIONS",
            normal_concurrency,
            legacy_max_connections,
        ),
        stream_max_connections=resolve_pool_size(
            "GATEWAY_STREAM_MAX_CONNECTIONS",
            stream_concurrency,
            legacy_max_connections,
        ),
        non_stream_max_keepalive_connections=resolve_pool_size(
            "GATEWAY_NON_STREAM_MAX_KEEPALIVE_CONNECTIONS",
            normal_concurrency,
            legacy_keepalive,
        ),
        stream_max_keepalive_connections=resolve_pool_size(
            "GATEWAY_STREAM_MAX_KEEPALIVE_CONNECTIONS",
            stream_concurrency,
            legacy_keepalive,
        ),
        keepalive_expiry_seconds=get_env_float(
            "GATEWAY_KEEPALIVE_EXPIRY_SECONDS",
            DEFAULT_KEEPALIVE_EXPIRY_SECONDS,
        ),
    )
