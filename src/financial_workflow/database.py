"""Database engine construction and readiness checks."""

from collections.abc import Callable

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ReadinessCheck = Callable[[], bool]


def build_engine(database_url: str) -> Engine:
    """Create a lazily connecting SQLAlchemy engine."""
    return create_engine(database_url, pool_pre_ping=True)


class DatabaseReadiness:
    """Report whether PostgreSQL can serve a trivial query."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def check(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

