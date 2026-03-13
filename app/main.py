"""Kimi Coding Plan Gateway."""

from __future__ import annotations

import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request

from app.config import GatewayConfig, load_config
from app.proxy import forward_request
from app.runtime import GatewayRuntime, close_runtime, create_runtime

CONFIG = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = create_runtime(CONFIG)
    app.state.runtime = runtime
    try:
        yield
    finally:
        await close_runtime(runtime)


app = FastAPI(title="Kimi Coding Plan Gateway", lifespan=lifespan)


def get_runtime(request: Request) -> GatewayRuntime:
    return request.app.state.runtime


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_v1(path: str, request: Request):
    runtime = get_runtime(request)
    target_url = f"{runtime.config.kimi_base_url}/{path}"
    return await forward_request(runtime, target_url, request)


@app.get("/")
async def root(request: Request):
    runtime = get_runtime(request)
    return {
        "status": "running",
        "service": "Kimi Coding Plan Gateway",
        "kimi_base_url": CONFIG.kimi_base_url,
        "gateway_url": f"http://{CONFIG.gateway_host}:{CONFIG.gateway_port}",
        "user_agent": CONFIG.kimi_cli_user_agent,
        "debug_mode": CONFIG.debug_mode,
        "debug_jsonl_file": CONFIG.debug_jsonl_file,
        "non_stream_max_upstream_concurrency": CONFIG.non_stream_max_upstream_concurrency,
        "stream_max_upstream_concurrency": CONFIG.stream_max_upstream_concurrency,
        "metrics": runtime.metrics.snapshot(runtime.normal_gate, runtime.stream_gate),
    }


@app.get("/health")
async def health(request: Request):
    runtime = get_runtime(request)
    return {
        "status": "ok",
        "active_streams": runtime.metrics.snapshot(runtime.normal_gate, runtime.stream_gate)["active_streams"],
    }


@app.get("/metrics")
async def metrics(request: Request):
    runtime = get_runtime(request)
    return runtime.metrics.snapshot(runtime.normal_gate, runtime.stream_gate)


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def print_startup_banner(config: GatewayConfig):
    print("[INFO] 启动 Kimi Coding Plan Gateway...")
    print(f"[INFO] 监听地址: http://{config.gateway_host}:{config.gateway_port}")
    print(f"[INFO] 普通请求并发上限: {config.non_stream_max_upstream_concurrency}")
    print(f"[INFO] 流式请求并发上限: {config.stream_max_upstream_concurrency}")
    if config.gateway_host != "0.0.0.0":
        return
    local_ip = get_local_ip()
    print(f"[INFO] 局域网访问地址: http://{local_ip}:{config.gateway_port}")
    print("[WARN] 注意：允许外部访问可能导致 API Key 被局域网内其他人使用")


def start_gateway():
    print_startup_banner(CONFIG)
    uvicorn.run(app, host=CONFIG.gateway_host, port=CONFIG.gateway_port)


if __name__ == "__main__":
    start_gateway()
