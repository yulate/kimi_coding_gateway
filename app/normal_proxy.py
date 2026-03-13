from __future__ import annotations

import asyncio
import contextlib

from fastapi import Request
from fastapi.responses import Response

from app.debug_utils import parse_json_payload
from app.errors import GatewayError, build_request_deadline_error, normalize_gateway_exception
from app.request_utils import append_debug_record, build_upstream_request
from app.response_utils import REQUEST_ID_HEADER, build_json_error_response, filter_response_headers


class DownstreamDisconnected(Exception):
    pass


async def handle_normal_request(
    runtime,
    request: Request,
    target_url: str,
    body: bytes,
    debug_context: dict,
    started_at: float,
    deadline_at: float,
):
    runtime.metrics.record_request_start(False)
    response = None
    lease = None
    try:
        lease = await runtime.normal_gate.acquire()
        req = build_upstream_request(
            runtime.normal_client,
            runtime.config.kimi_api_key,
            runtime.config.kimi_cli_user_agent,
            request.method,
            target_url,
            body,
        )
        response = await _send_request(runtime, request, req, deadline_at)
        runtime.metrics.record_first_byte(False, _elapsed_since(started_at))
        content = await _read_response(runtime, request, response, deadline_at)
    except DownstreamDisconnected:
        await append_debug_record(
            runtime,
            debug_context,
            status_code=499,
            upstream_exception="downstream client disconnected",
        )
        runtime.metrics.record_request_complete(_elapsed_since(started_at))
        return Response(status_code=499)
    except Exception as exc:
        error = normalize_gateway_exception(exc)
        _record_deadline_metric(runtime, error)
        await append_debug_record(
            runtime,
            debug_context,
            status_code=error.status_code,
            upstream_exception=error.message,
        )
        runtime.metrics.record_request_complete(_elapsed_since(started_at))
        return build_json_error_response(error, debug_context["request_id"])
    finally:
        if response is not None:
            await response.aclose()
        if lease is not None:
            lease.release()
    response_json = None
    if runtime.debug_writer.enabled:
        response_json = parse_json_payload(content)
    await append_debug_record(runtime, debug_context, response.status_code, response_json)
    runtime.metrics.record_request_complete(_elapsed_since(started_at))
    headers = filter_response_headers(response.headers)
    headers[REQUEST_ID_HEADER] = debug_context["request_id"]
    return Response(content=content, status_code=response.status_code, headers=headers)


async def _send_request(runtime, request: Request, req, deadline_at: float):
    return await _await_or_disconnect(
        runtime.normal_client.send(req, stream=True),
        request,
        runtime.config.disconnect_poll_interval_seconds,
        deadline_at,
    )


async def _read_response(runtime, request: Request, response, deadline_at: float):
    return await _await_or_disconnect(
        response.aread(),
        request,
        runtime.config.disconnect_poll_interval_seconds,
        deadline_at,
    )


async def _await_or_disconnect(awaitable, request: Request, poll_interval: float, deadline_at: float):
    disconnect_task = asyncio.create_task(_wait_for_disconnect(request, poll_interval))
    awaitable_task = asyncio.create_task(awaitable)
    try:
        done, _ = await asyncio.wait(
            {awaitable_task, disconnect_task},
            timeout=_remaining_timeout(deadline_at),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            raise build_request_deadline_error()
        if disconnect_task in done:
            raise DownstreamDisconnected()
        return awaitable_task.result()
    finally:
        await _cleanup_task(awaitable_task)
        await _cleanup_task(disconnect_task)


async def _wait_for_disconnect(request: Request, poll_interval_seconds: float):
    while True:
        if await request.is_disconnected():
            raise DownstreamDisconnected()
        await asyncio.sleep(poll_interval_seconds)


def _remaining_timeout(deadline_at: float) -> float:
    remaining = deadline_at - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise build_request_deadline_error()
    return remaining


def _elapsed_since(started_at: float) -> float:
    return asyncio.get_running_loop().time() - started_at


def _record_deadline_metric(runtime, error: GatewayError):
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
