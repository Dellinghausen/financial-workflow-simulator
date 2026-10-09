"""Transactional background job worker."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from time import sleep
from typing import Protocol
from uuid import UUID


class JobKind(StrEnum):
    PROCESS_PAYMENT = "PROCESS_PAYMENT"


@dataclass(frozen=True, slots=True)
class Job:
    id: UUID
    kind: JobKind
    payload: dict[str, str]
    attempts: int


class JobQueue(Protocol):
    def claim_next(self, *, worker_id: str, now: datetime) -> Job | None: ...

    def complete(self, job: Job, *, worker_id: str, now: datetime) -> None: ...

    def retry(
        self,
        job: Job,
        *,
        worker_id: str,
        now: datetime,
        available_at: datetime,
        error: str,
    ) -> None: ...

    def fail(self, job: Job, *, worker_id: str, now: datetime, error: str) -> None: ...


class JobHandler(Protocol):
    def handle(self, job: Job, *, now: datetime) -> None: ...


class PaymentProcessingPort(Protocol):
    def start_processing(self, payment_id: UUID, *, now: datetime) -> None: ...


class ProcessPaymentJobHandler:
    def __init__(self, payments: PaymentProcessingPort) -> None:
        self._payments = payments

    def handle(self, job: Job, *, now: datetime) -> None:
        self._payments.start_processing(UUID(job.payload["payment_id"]), now=now)


class Worker:
    """Claim one job at a time and acknowledge only after successful handling."""

    def __init__(
        self,
        queue: JobQueue,
        handlers: Mapping[JobKind, JobHandler],
        *,
        worker_id: str,
        max_attempts: int = 3,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._queue = queue
        self._handlers = handlers
        self._worker_id = worker_id
        self._max_attempts = max_attempts
        self._clock = clock

    def run_once(self) -> bool:
        now = self._clock()
        job = self._queue.claim_next(worker_id=self._worker_id, now=now)
        if job is None:
            return False

        try:
            self._handlers[job.kind].handle(job, now=now)
        except Exception as error:
            message = str(error)[:500]
            if job.attempts >= self._max_attempts:
                self._queue.fail(job, worker_id=self._worker_id, now=now, error=message)
            else:
                delay = timedelta(seconds=min(2**job.attempts, 60))
                self._queue.retry(
                    job,
                    worker_id=self._worker_id,
                    now=now,
                    available_at=now + delay,
                    error=message,
                )
            return True

        self._queue.complete(job, worker_id=self._worker_id, now=now)
        return True

    def run_forever(self, *, poll_interval_seconds: float = 1.0) -> None:
        while True:
            if not self.run_once():
                sleep(poll_interval_seconds)

