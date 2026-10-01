from collections.abc import Callable

import pytest
import uvicorn
from fastapi.testclient import TestClient

from financial_workflow.main import create_app, run


def test_health_endpoint_reports_version() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_run_starts_the_local_server(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def capture_run(application: str, **options: object) -> None:
        captured.update(application=application, **options)

    replacement: Callable[..., None] = capture_run
    monkeypatch.setattr(uvicorn, "run", replacement)

    run()

    assert captured == {
        "application": "financial_workflow.main:app",
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
    }
