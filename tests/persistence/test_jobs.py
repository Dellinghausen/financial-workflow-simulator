from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from financial_workflow.application.jobs import Job, JobKind
from financial_workflow.persistence.jobs import JobLeaseLostError, PostgreSQLJobQueue
from financial_workflow.persistence.models import JobRecord

JOB_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a122")
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def build_queue() -> tuple[PostgreSQLJobQueue, MagicMock]:
    sessions = MagicMock()
    session = sessions.begin.return_value.__enter__.return_value
    return PostgreSQLJobQueue(sessions), session


def build_record() -> JobRecord:
    return JobRecord(
        id=JOB_ID,
        kind="PROCESS_PAYMENT",
        payload={"payment_id": "018f47d2-a97c-7f18-bb5c-d53f8b86a121"},
        status="READY",
        attempts=0,
        available_at=NOW,
        locked_at=None,
        locked_by=None,
        last_error=None,
        created_at=NOW,
        updated_at=NOW,
    )


def test_claim_returns_none_when_no_job_is_available() -> None:
    queue, session = build_queue()
    session.execute.return_value.scalar_one_or_none.return_value = None

    assert queue.claim_next(worker_id="worker-1", now=NOW) is None


def test_claim_acquires_lease_and_increments_attempts() -> None:
    queue, session = build_queue()
    record = build_record()
    session.execute.return_value.scalar_one_or_none.return_value = record

    job = queue.claim_next(worker_id="worker-1", now=NOW)

    assert job == Job(JOB_ID, JobKind.PROCESS_PAYMENT, record.payload, 1)
    assert record.status == "PROCESSING"
    assert record.locked_by == "worker-1"
    assert record.locked_at == NOW
    assert record.attempts == 1


@pytest.mark.parametrize("action", ["complete", "retry", "fail"])
def test_job_outcomes_require_the_current_lease(action: str) -> None:
    queue, session = build_queue()
    session.execute.return_value.rowcount = 1
    job = Job(JOB_ID, JobKind.PROCESS_PAYMENT, {}, 1)

    if action == "complete":
        queue.complete(job, worker_id="worker-1", now=NOW)
    elif action == "retry":
        queue.retry(
            job,
            worker_id="worker-1",
            now=NOW,
            available_at=NOW + timedelta(seconds=2),
            error="temporary",
        )
    else:
        queue.fail(job, worker_id="worker-1", now=NOW, error="permanent")

    session.execute.assert_called_once()


def test_job_outcome_rejects_a_lost_lease() -> None:
    queue, session = build_queue()
    session.execute.return_value.rowcount = 0
    job = Job(JOB_ID, JobKind.PROCESS_PAYMENT, {}, 1)

    with pytest.raises(JobLeaseLostError):
        queue.complete(job, worker_id="stale-worker", now=NOW)

