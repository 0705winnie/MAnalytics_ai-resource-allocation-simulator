"""SQLAlchemy engine, session factory, and FastAPI database dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_settings


database_settings = get_database_settings()

engine: Engine = create_engine(
    database_settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for a future FastAPI dependency."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
