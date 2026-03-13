import asyncio
import json
import unittest

import httpx

from app.concurrency import ConcurrencyGate
from app.errors import GatewayError, normalize_gateway_exception
from app.metrics import RuntimeMetrics
from app.normal_proxy import DownstreamDisconnected as NormalDownstreamDisconnected
from app.normal_proxy import _cleanup_task as cleanup_normal_task
from app.stream_proxy import DownstreamDisconnected as StreamDownstreamDisconnected
from app.stream_proxy import _cleanup_task as cleanup_stream_task
from app.request_utils import process_request_body
from app.response_utils import filter_response_headers


class ConcurrencyGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_timeout_raises_gateway_error(self):
        gate = ConcurrencyGate("test", max_concurrency=1, max_queue_size=1, acquire_timeout=0.01)
        first_lease = await gate.acquire()
        with self.assertRaises(GatewayError) as context:
            await gate.acquire()
        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.error_type, "test_queue_timeout")
        first_lease.release()

    async def test_queue_full_rejects_immediately(self):
        gate = ConcurrencyGate("test", max_concurrency=1, max_queue_size=1, acquire_timeout=0.1)
        first_lease = await gate.acquire()
        waiting_task = asyncio.create_task(gate.acquire())
        await asyncio.sleep(0.01)
        with self.assertRaises(GatewayError) as context:
            await gate.acquire()
        self.assertEqual(context.exception.error_type, "test_queue_full")
        first_lease.release()
        second_lease = await waiting_task
        second_lease.release()


class ProxyRequestBodyTests(unittest.TestCase):
    def test_process_request_body_injects_reasoning(self):
        payload = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"},
            ]
        }
        body, stream = process_request_body(
            json.dumps(payload).encode("utf-8"),
            "high",
        )
        self.assertFalse(stream)
        self.assertIn(b'"reasoning_effort": "high"', body)
        self.assertIn(b'"reasoning_content": " "', body)


class ErrorMappingTests(unittest.TestCase):
    def test_remote_protocol_error_maps_to_502(self):
        error = normalize_gateway_exception(httpx.RemoteProtocolError("boom"))
        self.assertEqual(error.status_code, 502)
        self.assertEqual(error.error_type, "upstream_protocol_error")

    def test_timeout_error_maps_to_gateway_deadline(self):
        error = normalize_gateway_exception(TimeoutError())
        self.assertEqual(error.status_code, 504)
        self.assertEqual(error.error_type, "gateway_request_deadline_exceeded")


class ResponseHeaderTests(unittest.TestCase):
    def test_filter_response_headers_removes_content_encoding(self):
        headers = httpx.Headers(
            {
                "content-encoding": "gzip",
                "content-type": "application/json",
            }
        )
        filtered = filter_response_headers(headers)
        self.assertNotIn("content-encoding", filtered)
        self.assertEqual(filtered["content-type"], "application/json")


class MetricsTests(unittest.TestCase):
    def test_snapshot_contains_gate_and_stream_metrics(self):
        metrics = RuntimeMetrics()
        normal_gate = ConcurrencyGate("normal", 2, 2, 0.01)
        stream_gate = ConcurrencyGate("stream", 1, 1, 0.01)
        metrics.record_request_start(False)
        metrics.record_request_start(True)
        metrics.record_first_byte(False, 0.2)
        metrics.record_first_byte(True, 0.4)
        metrics.record_stream_started()
        metrics.record_stream_finished()
        metrics.record_request_complete(1.5)
        snapshot = metrics.snapshot(normal_gate, stream_gate)
        self.assertEqual(snapshot["request_total"], 2)
        self.assertEqual(snapshot["stream_first_byte"]["avg_seconds"], 0.4)
        self.assertIn("normal_gate", snapshot)
        self.assertIn("stream_gate", snapshot)


class TaskCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_cleanup_consumes_finished_exception_task(self):
        async def boom():
            raise NormalDownstreamDisconnected()

        task = asyncio.create_task(boom())
        await asyncio.sleep(0)
        await cleanup_normal_task(task)

    async def test_stream_cleanup_consumes_finished_exception_task(self):
        async def boom():
            raise StreamDownstreamDisconnected()

        task = asyncio.create_task(boom())
        await asyncio.sleep(0)
        await cleanup_stream_task(task)


if __name__ == "__main__":
    unittest.main()
