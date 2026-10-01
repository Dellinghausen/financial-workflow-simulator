from collections.abc import Callable

import pytest
import uvicorn
from fastapi.testclient import TestClient

from financial_workflow.main import create_app, run


def test_health_endpoint_reports_version() -> None:
    response = TestClient(create_app(readiness_check=lambda: True)).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_liveness_does_not_depend_on_the_database() -> None:
    response = TestClient(create_app(readiness_check=lambda: False)).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


@pytest.mark.parametrize(
    ("database_is_ready", "expected_status", "expected_body"),
    [
        (True, 200, {"status": "ready"}),
        (False, 503, {"status": "unavailable"}),
    ],
)
def test_readiness_reflects_database_availability(
    database_is_ready: bool,
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    response = TestClient(
        create_app(readiness_check=lambda: database_is_ready)
    ).get("/health/ready")

    assert response.status_code == expected_status
    assert response.json() == expected_body


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
