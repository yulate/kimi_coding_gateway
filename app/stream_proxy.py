from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.debug_utils import parse_json_payload, parse_stream_json_events
from app.errors import build_request_deadline_error, normalize_gateway_exception
from app.request_utils import append_debug_record, build_upstream_request
from app.response_utils import (
    REQUEST_ID_HEADER,
    build_error_payload,
    build_stream_error_response,
    build_upstream_status_error,
)


class DownstreamDisconnected(Exception):
    pass


async def handle_stream_request(
    runtime,
    request: Request,
    target_url: str,
    body: bytes,
    debug_context: dict,
    started_at: float,
    deadline_at: float,
):
    runtime.metrics.record_request_start(True)
    lease = None
    response = None
    try:
        lease = await runtime.stream_gate.acquire()
        req = build_upstream_request(
            runtime.stream_client,
            runtime.config.kimi_api_key,
            runtime.config.kimi_cli_user_agent,
            request.method,
            target_url,
            body,
        )
        response = await asyncio.wait_for(
            runtime.stream_client.send(req, stream=True),
            timeout=_remaining_timeout(deadline_at),
        )
    except Exception as exc:
        error = normalize_gateway_exception(exc)
        _record_deadline_metric(runtime, error)
        if lease is not None:
            lease.release()
        await append_debug_record(
            runtime,
            debug_context,
            status_code=error.status_code,
            upstream_exception=error.message,
        )
        runtime.metrics.record_request_complete(_elapsed_since(started_at))
        return build_stream_error_response(error, debug_context["request_id"])
    if response.status_code != 200:
        return await _handle_non_success_response(
            runtime,
            response,
            lease,
            debug_context,
            started_at,
            deadline_at,
        )
    runtime.metrics.record_stream_started()
    headers = {REQUEST_ID_HEADER: debug_context["request_id"]}
    return StreamingResponse(
        _stream_chunks(
            runtime,
            request,
            response,
            lease,
            debug_context,
            started_at,
            deadline_at,
        ),
        media_type="text/event-stream",
        status_code=response.status_code,
        headers=headers,
    )


async def _handle_non_success_response(
    runtime,
    response,
    lease,
    debug_context: dict,
    started_at: float,
    deadline_at: float,
):
    content = await asyncio.wait_for(
        response.aread(),
        timeout=_remaining_timeout(deadline_at),
    )
    error = build_upstream_status_error(response.status_code, content)
    response_json = None
    if runtime.debug_writer.enabled:
        response_json = parse_json_payload(content)
    await append_debug_record(
        runtime,
        debug_context,
        status_code=response.status_code,
        response_json=response_json,
        upstream_exception=error.message,
    )
    await response.aclose()
    lease.release()
    runtime.metrics.record_request_complete(_elapsed_since(started_at))
    return build_stream_error_response(error, debug_context["request_id"])


async def _stream_chunks(
    runtime,
    request: Request,
    response,
    lease,
    debug_context: dict,
    started_at: float,
    deadline_at: float,
):
    iterator = response.aiter_bytes()
    disconnect_task = asyncio.create_task(
        _wait_for_disconnect(request, runtime.config.disconnect_poll_interval_seconds)
    )
    raw_stream = bytearray() if runtime.debug_writer.enabled else None
    first_chunk_seen = False
    stream_error = None
    disconnected = False
    try:
        while True:
            chunk = await _next_chunk(iterator, disconnect_task, deadline_at)
            if chunk is None:
                break
            if not first_chunk_seen:
                runtime.metrics.record_first_byte(True, _elapsed_since(started_at))
                first_chunk_seen = True
            if raw_stream is not None:
                raw_stream.extend(chunk)
            yield chunk
    except DownstreamDisconnected:
        disconnected = True
        runtime.metrics.record_client_disconnect()
    except Exception as exc:
        stream_error = normalize_gateway_exception(exc)
        _record_deadline_metric(runtime, stream_error)
        payload = build_error_payload(stream_error, debug_context["request_id"])
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
        yield b"data: [DONE]\n\n"
    finally:
        await _cleanup_task(disconnect_task)
        await response.aclose()
        lease.release()
        await _finalize_stream(
            runtime,
            debug_context,
            response.status_code,
            raw_stream,
            stream_error,
            disconnected,
        )
        runtime.metrics.record_stream_finished()
        runtime.metrics.record_request_complete(_elapsed_since(started_at))


async def _next_chunk(iterator, disconnect_task, deadline_at: float):
    chunk_task = asyncio.create_task(iterator.__anext__())
    try:
        done, _ = await asyncio.wait(
            {chunk_task, disconnect_task},
            timeout=_remaining_timeout(deadline_at),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            raise build_request_deadline_error()
        if disconnect_task in done:
            raise DownstreamDisconnected()
        return chunk_task.result()
    except StopAsyncIteration:
        return None
    finally:
        await _cleanup_task(chunk_task)


async def _wait_for_disconnect(request: Request, poll_interval_seconds: float):
    while True:
        if await request.is_disconnected():
            raise DownstreamDisconnected()
        await asyncio.sleep(poll_interval_seconds)


async def _finalize_stream(
    runtime,
    debug_context: dict,
    status_code: int,
    raw_stream: bytearray | None,
    stream_error,
    disconnected: bool,
):
    response_json = None
    if raw_stream is not None:
        response_json = parse_stream_json_events(bytes(raw_stream))
    error_message = None if stream_error is None else stream_error.message
    if disconnected:
        error_message = "downstream client disconnected"
    await append_debug_record(
        runtime,
        debug_context,
        status_code=status_code,
        response_json=response_json,
        upstream_exception=error_message,
    )


def _remaining_timeout(deadline_at: float) -> float:
    remaining = deadline_at - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise build_request_deadline_error()
    return remaining


def _elapsed_since(started_at: float) -> float:
    return asyncio.get_running_loop().time() - started_at


def _record_deadline_metric(runtime, error):
    if error.error_type != "gateway_request_deadline_exceeded":
        return
    runtime.metrics.record_deadline_exceeded()


async def _cleanup_task(task: asyncio.Task):
    if not task.done():
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
        return
    with contextlib.suppress(BaseException):
        task.result()
