from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI.unicode_string(), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator:
    session = None
    try:
        session = SessionLocal()
        yield session
    finally:
        if session:
            session.close()


db_context = contextmanager(get_db_session)
