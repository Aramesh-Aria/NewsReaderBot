import os
import logging
from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from NewsBot.models import Base

logger = logging.getLogger(__name__)


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set in environment variables.")
    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = _get_database_url()

    echo = os.getenv("SQLALCHEMY_ECHO", "").strip() == "1"
    connect_args = {}

    # Sensible defaults for Postgres; safe fallback for SQLite.
    if database_url.startswith("sqlite"):
        # Avoid cross-thread issues if PTB uses threads internally.
        connect_args["check_same_thread"] = False
        engine = create_engine(
            database_url,
            echo=echo,
            connect_args=connect_args,
            poolclass=NullPool,
        )
        return engine

    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    engine = create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
    )
    return engine


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker:
    engine = get_engine()
    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@contextmanager
def session_scope(*, commit: bool = True) -> Generator[Session, None, None]:
    SessionLocal = get_sessionmaker()
    session: Session = SessionLocal()
    try:
        yield session
        if commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(*, create_tables: bool = False) -> Engine:
    """
    Initialize the DB engine once at startup.

    In production, prefer migrations (Alembic) and keep create_tables=False.
    """
    engine = get_engine()
    if create_tables:
        Base.metadata.create_all(engine)
        logger.info("Database tables ensured via SQLAlchemy create_all().")
    return engine
