"""Database engine and connectivity checks."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.models import Base


def build_engine(settings: Settings) -> Engine:
    url = settings.resolved_database_url()
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": settings.database_connect_timeout},
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def database_error(engine: Engine) -> Exception | None:
    """Return an exception when SELECT 1 fails, otherwise None."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - connectivity probe must catch driver errors
        return exc
    return None


def ensure_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
