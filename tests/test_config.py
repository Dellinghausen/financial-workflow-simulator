import pytest

from financial_workflow.config import Settings


def test_settings_are_loaded_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Environment integration is covered here without exposing secret values in output.
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@database/test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.database_url == "postgresql+psycopg://test:test@database/test"
    assert settings.log_level == "DEBUG"
    assert settings.webhook_secret.get_secret_value() == "test-secret"
