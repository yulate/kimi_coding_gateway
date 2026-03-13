from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import Request

from app.debug_utils import parse_json_payload


def process_request_body(body: bytes, default_reasoning_effort: str) -> tuple[bytes, bool]:
    if not body:
        return body, False
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body, False
    stream = data.get("stream", False)
    modified = False
    if data.get("messages") and "reasoning_effort" not in data:
        data["reasoning_effort"] = default_reasoning_effort
        modified = True
    for message in data.get("messages", []):
        if message.get("role") != "assistant":
            continue
        if "reasoning_content" in message:
            continue
        message["reasoning_content"] = " "
        modified = True
    if not modified:
        return body, stream
    return json.dumps(data).encode("utf-8"), stream


def build_debug_context(
    request: Request,
    target_url: str,
    stream: bool,
    request_json=None,
):
    context = {
        "request_id": uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "target_url": target_url,
        "stream": stream,
    }
    if request_json is not None:
        context["request_json"] = request_json
    return context


def build_upstream_request(
    client: httpx.AsyncClient,
    api_key: str,
    user_agent: str,
    method: str,
    target_url: str,
    body: bytes,
) -> httpx.Request:
    return client.build_request(
        method=method,
        url=target_url,
        content=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
    )


async def append_debug_record(
    runtime,
    debug_context: dict,
    status_code: int | None,
    response_json=None,
    upstream_exception: str | None = None,
):
    if not runtime.debug_writer.enabled:
        return
    record = {**debug_context, "status_code": status_code}
    if response_json is not None:
        record["response_json"] = response_json
    if upstream_exception is not None:
        record["upstream_exception"] = upstream_exception
    await runtime.debug_writer.append(record)


def parse_request_json(runtime, original_body: bytes):
    if not runtime.debug_writer.enabled:
        return None
    return parse_json_payload(original_body)
