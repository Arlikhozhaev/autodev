"""
Database engine, session factory, and declarative base.
All models import Base from here.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


def _engine_kwargs(database_url: str) -> dict:
    kwargs: dict = {
        "pool_pre_ping": True,
        "echo": settings.ENV == "development",
    }
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    return kwargs


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
