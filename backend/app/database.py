"""Database engine, session factory and declarative base.

SQLite file DB by default. Models avoid SQLite-only constructs so a swap to
Postgres is only a URL change.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# ``check_same_thread`` is a SQLite-specific requirement for FastAPI's
# threaded request handling; it is ignored by other drivers.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session that is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models for side-effect registration."""
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
