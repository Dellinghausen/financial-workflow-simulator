"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from sqlalchemy import Engine

from financial_workflow import __version__
from financial_workflow.config import get_settings
from financial_workflow.database import DatabaseReadiness, ReadinessCheck, build_engine


def create_app(readiness_check: ReadinessCheck | None = None) -> FastAPI:
    """Build the HTTP application without global side effects."""
    engine: Engine | None = None
    resolved_readiness_check = readiness_check
    if resolved_readiness_check is None:
        engine = build_engine(get_settings().database_url)
        resolved_readiness_check = DatabaseReadiness(engine).check

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
