from datetime import UTC, datetime, timedelta
from uuid import UUID

from financial_workflow.application.jobs import (
    Job,
    JobKind,
    ProcessPaymentJobHandler,
    Worker,
)

JOB_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a122")
PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


class RecordingQueue:
    def __init__(self, job: Job | None) -> None:
        self.job = job
        self.action: tuple[object, ...] | None = None

    def claim_next(self, *, worker_id: str, now: datetime) -> Job | None:
        self.claim = (worker_id, now)
        return self.job

    def complete(self, job: Job, *, worker_id: str, now: datetime) -> None:
        self.action = ("complete", job, worker_id, now)

    def retry(
        self,
        job: Job,
        *,
        worker_id: str,
        now: datetime,
        available_at: datetime,
        error: str,
    ) -> None:
        self.action = ("retry", job, worker_id, now, available_at, error)

    def fail(self, job: Job, *, worker_id: str, now: datetime, error: str) -> None:
        self.action = ("fail", job, worker_id, now, error)


class RecordingHandler:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.handled: Job | None = None

    def handle(self, job: Job, *, now: datetime) -> None:
        self.handled = job
        if self.error is not None:
            raise self.error


def build_job(*, attempts: int = 1) -> Job:
    return Job(JOB_ID, JobKind.PROCESS_PAYMENT, {"payment_id": str(PAYMENT_ID)}, attempts)


def test_worker_returns_false_when_queue_is_empty() -> None:
    queue = RecordingQueue(None)
    worker = Worker(queue, {}, worker_id="worker-1", clock=lambda: NOW)

    assert worker.run_once() is False
    assert queue.action is None


def test_worker_completes_successful_job() -> None:
    job = build_job()
    queue = RecordingQueue(job)
    handler = RecordingHandler()
    worker = Worker(
        queue,
        {JobKind.PROCESS_PAYMENT: handler},
        worker_id="worker-1",
        clock=lambda: NOW,
    )

    assert worker.run_once() is True
    assert handler.handled == job
    assert queue.action == ("complete", job, "worker-1", NOW)


def test_worker_retries_failure_with_exponential_backoff() -> None:
    job = build_job(attempts=2)
    queue = RecordingQueue(job)
    worker = Worker(
        queue,
        {JobKind.PROCESS_PAYMENT: RecordingHandler(RuntimeError("temporary"))},
        worker_id="worker-1",
        clock=lambda: NOW,
    )

    assert worker.run_once() is True
    assert queue.action == (
        "retry",
        job,
        "worker-1",
        NOW,
        NOW + timedelta(seconds=4),
        "temporary",
    )


def test_worker_permanently_fails_after_attempt_limit() -> None:
    job = build_job(attempts=3)
    queue = RecordingQueue(job)
    worker = Worker(
        queue,
        {JobKind.PROCESS_PAYMENT: RecordingHandler(RuntimeError("permanent"))},
        worker_id="worker-1",
        clock=lambda: NOW,
    )

    assert worker.run_once() is True
    assert queue.action == ("fail", job, "worker-1", NOW, "permanent")


def test_payment_handler_parses_payment_identity() -> None:
    payments = RecordingPayments()

    ProcessPaymentJobHandler(payments).handle(build_job(), now=NOW)

    assert payments.call == (PAYMENT_ID, NOW)


class RecordingPayments:
    def __init__(self) -> None:
        self.call: tuple[UUID, datetime] | None = None

    def start_processing(self, payment_id: UUID, *, now: datetime) -> None:
        self.call = (payment_id, now)

