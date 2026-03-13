from __future__ import annotations

from app.concurrency import ConcurrencyGate


class RuntimeMetrics:
    def __init__(self):
        self._request_total = 0
        self._normal_request_total = 0
        self._stream_request_total = 0
        self._request_duration_total_seconds = 0.0
        self._request_duration_samples = 0
        self._normal_first_byte_total_seconds = 0.0
        self._normal_first_byte_samples = 0
        self._stream_first_byte_total_seconds = 0.0
        self._stream_first_byte_samples = 0
        self._active_streams = 0
        self._max_active_streams = 0
        self._client_disconnect_total = 0
        self._deadline_exceeded_total = 0

    def record_request_start(self, stream: bool):
        self._request_total += 1
        if stream:
            self._stream_request_total += 1
            return
        self._normal_request_total += 1

    def record_request_complete(self, duration_seconds: float):
        self._request_duration_total_seconds += duration_seconds
        self._request_duration_samples += 1

    def record_first_byte(self, stream: bool, seconds: float):
        if stream:
            self._stream_first_byte_total_seconds += seconds
            self._stream_first_byte_samples += 1
            return
        self._normal_first_byte_total_seconds += seconds
        self._normal_first_byte_samples += 1

    def record_stream_started(self):
        self._active_streams += 1
        self._max_active_streams = max(self._max_active_streams, self._active_streams)

    def record_stream_finished(self):
        self._active_streams = max(0, self._active_streams - 1)

    def record_client_disconnect(self):
        self._client_disconnect_total += 1

    def record_deadline_exceeded(self):
        self._deadline_exceeded_total += 1

    def snapshot(
        self,
        normal_gate: ConcurrencyGate,
        stream_gate: ConcurrencyGate,
    ) -> dict:
        avg_request_duration_seconds = 0.0
        if self._request_duration_samples:
            avg_request_duration_seconds = (
                self._request_duration_total_seconds / self._request_duration_samples
            )
        return {
            "request_total": self._request_total,
            "normal_request_total": self._normal_request_total,
            "stream_request_total": self._stream_request_total,
            "avg_request_duration_seconds": avg_request_duration_seconds,
            "normal_first_byte": self._build_first_byte_snapshot(False),
            "stream_first_byte": self._build_first_byte_snapshot(True),
            "active_streams": self._active_streams,
            "max_active_streams": self._max_active_streams,
            "client_disconnect_total": self._client_disconnect_total,
            "deadline_exceeded_total": self._deadline_exceeded_total,
            "normal_gate": normal_gate.snapshot(),
            "stream_gate": stream_gate.snapshot(),
        }

    def _build_first_byte_snapshot(self, stream: bool) -> dict:
        total = self._stream_first_byte_total_seconds if stream else self._normal_first_byte_total_seconds
        samples = self._stream_first_byte_samples if stream else self._normal_first_byte_samples
        avg_seconds = 0.0
        if samples:
            avg_seconds = total / samples
        return {
            "samples": samples,
            "total_seconds": total,
            "avg_seconds": avg_seconds,
        }
