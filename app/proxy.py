from __future__ import annotations

import asyncio

from fastapi import Request

from app.normal_proxy import handle_normal_request
from app.request_utils import build_debug_context, parse_request_json, process_request_body
from app.stream_proxy import handle_stream_request


async def forward_request(runtime, target_url: str, request: Request):
    started_at = asyncio.get_running_loop().time()
    deadline_at = started_at + runtime.config.request_deadline_seconds
    original_body = await request.body()
    body, stream = process_request_body(
        original_body,
        runtime.config.default_reasoning_effort,
    )
    request_json = parse_request_json(runtime, original_body)
    debug_context = build_debug_context(request, target_url, stream, request_json)
    if request_json is not None:
        debug_context["forwarded_request_json"] = parse_request_json(runtime, body)
    if stream:
        return await handle_stream_request(
            runtime,
            request,
            target_url,
            body,
            debug_context,
            started_at,
            deadline_at,
        )
    return await handle_normal_request(
        runtime,
        request,
        target_url,
        body,
        debug_context,
        started_at,
        deadline_at,
    )
