from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter

from app.errors import GatewayError


@dataclass
class ConcurrencyLease:
    gate: "ConcurrencyGate"
    queue_wait_seconds: float
    released: bool = False

    def release(self):
        if self.released:
            return
        self.released = True
        self.gate.release()


class ConcurrencyGate:
    def __init__(
        self,
        name: str,
        max_concurrency: int,
        max_queue_size: int,
        acquire_timeout: float,
    ):
        self._name = name
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_concurrency = max_concurrency
        self._max_queue_size = max_queue_size
        self._acquire_timeout = acquire_timeout
        self._in_flight = 0
        self._waiters = 0
        self._max_observed_in_flight = 0
        self._queue_wait_total_seconds = 0.0
        self._queue_wait_samples = 0
        self._acquired_total = 0
        self._queue_full_total = 0
        self._queue_timeout_total = 0

    async def acquire(self) -> ConcurrencyLease:
        self._reject_if_queue_full()
        wait_started_at = perf_counter()
        self._waiters += 1
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._acquire_timeout,
            )
        except TimeoutError as exc:
            self._queue_timeout_total += 1
            raise GatewayError(
                503,
                f"{self._name}_queue_timeout",
                f"Timed out waiting for a {self._name} upstream slot.",
            ) from exc
        finally:
            self._waiters -= 1
        queue_wait_seconds = perf_counter() - wait_started_at
        self._queue_wait_total_seconds += queue_wait_seconds
        self._queue_wait_samples += 1
        self._acquired_total += 1
        self._in_flight += 1
        self._max_observed_in_flight = max(
            self._max_observed_in_flight,
            self._in_flight,
        )
        return ConcurrencyLease(self, queue_wait_seconds)

    def release(self):
        self._in_flight -= 1
        self._semaphore.release()

    def snapshot(self) -> dict:
        avg_queue_wait_seconds = 0.0
        if self._queue_wait_samples:
            avg_queue_wait_seconds = (
                self._queue_wait_total_seconds / self._queue_wait_samples
            )
        return {
            "name": self._name,
            "max_concurrency": self._max_concurrency,
            "max_queue_size": self._max_queue_size,
            "in_flight": self._in_flight,
            "waiters": self._waiters,
            "max_observed_in_flight": self._max_observed_in_flight,
            "acquired_total": self._acquired_total,
            "queue_wait_samples": self._queue_wait_samples,
            "queue_wait_total_seconds": self._queue_wait_total_seconds,
            "avg_queue_wait_seconds": avg_queue_wait_seconds,
            "queue_full_total": self._queue_full_total,
            "queue_timeout_total": self._queue_timeout_total,
        }

    def _reject_if_queue_full(self):
        if self._waiters < self._max_queue_size:
            return
        self._queue_full_total += 1
        raise GatewayError(
            503,
            f"{self._name}_queue_full",
            f"{self._name} queue is full.",
        )
