from datetime import UTC, datetime, timedelta
from uuid import UUID

from financial_workflow.application.jobs import (
    Job,
    JobKind,
    ProcessPaymentJobHandler,
    Worker,
)
from financial_workflow.application.providers import (
    PermanentProviderError,
    ProviderScenario,
    ProviderSubmission,
)
from financial_workflow.domain import Currency, Money, Payment

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
        self.exhausted: tuple[Job, datetime, Exception] | None = None

    def handle(self, job: Job, *, now: datetime) -> None:
        self.handled = job
        if self.error is not None:
            raise self.error

    def on_exhausted(self, job: Job, *, now: datetime, error: Exception) -> None:
        self.exhausted = (job, now, error)


def build_job(*, attempts: int = 1) -> Job:
    return Job(
        JOB_ID,
        JobKind.PROCESS_PAYMENT,
        {
            "payment_id": str(PAYMENT_ID),
            "provider_scenario": ProviderScenario.SUCCESS.value,
        },
        attempts,
    )


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
    handler = RecordingHandler(RuntimeError("permanent"))
    worker = Worker(
        queue,
        {JobKind.PROCESS_PAYMENT: handler},
        worker_id="worker-1",
        clock=lambda: NOW,
    )

    assert worker.run_once() is True
    assert queue.action == ("fail", job, "worker-1", NOW, "permanent")
    assert handler.exhausted is not None


def test_payment_handler_parses_payment_identity() -> None:
    payments = RecordingPayments()
    provider = RecordingProvider()

    ProcessPaymentJobHandler(payments, provider).handle(build_job(), now=NOW)

    assert payments.call == (PAYMENT_ID, NOW)
    assert provider.call is not None


def test_payment_handler_marks_permanent_provider_failure() -> None:
    payments = RecordingPayments()
    provider = RecordingProvider(PermanentProviderError("rejected"))

    ProcessPaymentJobHandler(payments, provider).handle(build_job(), now=NOW)

    assert payments.failed == (PAYMENT_ID, NOW)


def test_payment_handler_marks_payment_failed_after_retry_exhaustion() -> None:
    payments = RecordingPayments()
    handler = ProcessPaymentJobHandler(payments, RecordingProvider())

    handler.on_exhausted(build_job(attempts=3), now=NOW, error=TimeoutError())

    assert payments.failed == (PAYMENT_ID, NOW)


class RecordingPayments:
    def __init__(self) -> None:
        self.call: tuple[UUID, datetime] | None = None
        self.failed: tuple[UUID, datetime] | None = None

    def start_processing(self, payment_id: UUID, *, now: datetime) -> Payment:
        self.call = (payment_id, now)
        payment = Payment.create(
            payment_id=payment_id,
            money=Money(500, Currency.USD),
            now=NOW,
        )
        payment.start_processing(now=now)
        return payment

    def mark_failed(self, payment_id: UUID, *, now: datetime) -> None:
        self.failed = (payment_id, now)


class RecordingProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.call: tuple[Payment, ProviderScenario, int] | None = None

    def submit(
        self,
        payment: Payment,
        *,
        scenario: ProviderScenario,
        attempt: int,
    ) -> ProviderSubmission:
        self.call = (payment, scenario, attempt)
        if self.error is not None:
            raise self.error
        return ProviderSubmission("sim_reference")

