from unittest.mock import MagicMock

from sqlalchemy.exc import OperationalError

from financial_workflow.database import DatabaseReadiness


def test_database_readiness_succeeds_when_query_executes() -> None:
    engine = MagicMock()

    assert DatabaseReadiness(engine).check() is True
    engine.connect.return_value.__enter__.return_value.execute.assert_called_once()


def test_database_readiness_handles_database_errors() -> None:
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("offline"))

    assert DatabaseReadiness(engine).check() is False
