"""PostgreSQL transactional job queue."""

from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from financial_workflow.application.jobs import Job, JobKind
from financial_workflow.persistence.models import JobRecord


class JobLeaseLostError(RuntimeError):
    """The worker no longer owns the job it attempted to update."""


class PostgreSQLJobQueue:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        lease_duration: timedelta = timedelta(minutes=5),
    ) -> None:
        self._sessions = sessions
        self._lease_duration = lease_duration

    def claim_next(self, *, worker_id: str, now: datetime) -> Job | None:
        stale_before = now - self._lease_duration
        with self._sessions.begin() as session:
            record = session.execute(
                select(JobRecord)
                .where(
                    or_(
                        and_(
                            JobRecord.status == "READY",
                            JobRecord.available_at <= now,
                        ),
                        and_(
                            JobRecord.status == "PROCESSING",
                            JobRecord.locked_at <= stale_before,
                        ),
                    )
                )
                .order_by(JobRecord.available_at, JobRecord.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return None

            record.status = "PROCESSING"
            record.attempts += 1
            record.locked_at = now
            record.locked_by = worker_id
            record.updated_at = now
            return Job(
                id=record.id,
                kind=JobKind(record.kind),
                payload=record.payload,
                attempts=record.attempts,
            )

    def complete(self, job: Job, *, worker_id: str, now: datetime) -> None:
        self._finish(
            job,
            worker_id=worker_id,
            values={
                "status": "COMPLETED",
                "locked_at": None,
                "locked_by": None,
                "last_error": None,
                "updated_at": now,
            },
        )

    def retry(
        self,
        job: Job,
        *,
        worker_id: str,
        now: datetime,
        available_at: datetime,
        error: str,
    ) -> None:
        self._finish(
            job,
            worker_id=worker_id,
            values={
                "status": "READY",
                "available_at": available_at,
                "locked_at": None,
                "locked_by": None,
                "last_error": error,
                "updated_at": now,
            },
        )

    def fail(self, job: Job, *, worker_id: str, now: datetime, error: str) -> None:
        self._finish(
            job,
            worker_id=worker_id,
            values={
                "status": "FAILED",
                "locked_at": None,
                "locked_by": None,
                "last_error": error,
                "updated_at": now,
            },
        )

    def _finish(
        self,
        job: Job,
        *,
        worker_id: str,
        values: dict[str, object],
    ) -> None:
        with self._sessions.begin() as session:
            result = session.execute(
                update(JobRecord)
                .where(
                    JobRecord.id == job.id,
                    JobRecord.status == "PROCESSING",
                    JobRecord.locked_by == worker_id,
                )
                .values(**values)
            )
            if cast(CursorResult[Any], result).rowcount != 1:
                raise JobLeaseLostError(str(job.id))

