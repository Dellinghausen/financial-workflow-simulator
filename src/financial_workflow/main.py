"""FastAPI application entry point."""

from fastapi import FastAPI

from financial_workflow import __version__


def create_app() -> FastAPI:
    """Build the HTTP application without global side effects."""
    application = FastAPI(
        title="Financial Workflow Simulator",
        summary="A fictional system for demonstrating reliable financial workflows.",
        version=__version__,
    )

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return application


app = create_app()


def run() -> None:
    """Run the development HTTP server."""
    import uvicorn

    uvicorn.run("financial_workflow.main:app", host="127.0.0.1", port=8000, reload=False)
