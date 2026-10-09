"""Background worker process entry point."""

from os import getpid
from socket import gethostname

from sqlalchemy.orm import sessionmaker

from financial_workflow.application import JobKind, ProcessPaymentJobHandler, Worker
from financial_workflow.config import get_settings
from financial_workflow.database import build_engine
from financial_workflow.integrations import DeterministicProviderClient
from financial_workflow.persistence.jobs import PostgreSQLJobQueue
from financial_workflow.persistence.repositories import PostgreSQLPaymentProcessor


def build_worker() -> Worker:
    engine = build_engine(get_settings().database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    return Worker(
        PostgreSQLJobQueue(sessions),
        {
            JobKind.PROCESS_PAYMENT: ProcessPaymentJobHandler(
                PostgreSQLPaymentProcessor(sessions),
                DeterministicProviderClient(),
            )
        },
        worker_id=f"{gethostname()}:{getpid()}",
    )


def run() -> None:
    """Run the worker until the process receives a termination signal."""
    build_worker().run_forever()

