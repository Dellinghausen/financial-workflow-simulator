"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from financial_workflow import __version__
from financial_workflow.api.payments import build_payment_router
from financial_workflow.application import CreatePaymentHandler, CreatePaymentService
from financial_workflow.config import get_settings
from financial_workflow.database import DatabaseReadiness, ReadinessCheck, build_engine
from financial_workflow.persistence.repositories import PostgreSQLPaymentRepository


def create_app(
    readiness_check: ReadinessCheck | None = None,
    payment_handler: CreatePaymentHandler | None = None,
) -> FastAPI:
    """Build the HTTP application without global side effects."""
    engine: Engine | None = None
    resolved_readiness_check = readiness_check
    resolved_payment_handler = payment_handler
    if resolved_readiness_check is None or resolved_payment_handler is None:
        engine = build_engine(get_settings().database_url)
        if resolved_readiness_check is None:
            resolved_readiness_check = DatabaseReadiness(engine).check
        if resolved_payment_handler is None:
            sessions = sessionmaker(engine, expire_on_commit=False)
            resolved_payment_handler = CreatePaymentService(
                PostgreSQLPaymentRepository(sessions)
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            engine.dispose()

    application = FastAPI(
        title="Financial Workflow Simulator",
        summary="A fictional system for demonstrating reliable financial workflows.",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(build_payment_router(resolved_payment_handler))

    @application.get("/health", tags=["operations"])
    @application.get("/health/live", tags=["operations"])
    def liveness() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/health/ready", tags=["operations"])
    def readiness(response: Response) -> dict[str, str]:
        if not resolved_readiness_check():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unavailable"}
        return {"status": "ready"}

    return application


app = create_app()


def run() -> None:
    """Run the development HTTP server."""
    import uvicorn

    uvicorn.run("financial_workflow.main:app", host="127.0.0.1", port=8000, reload=False)
