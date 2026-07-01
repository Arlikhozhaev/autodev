"""
Database migration bootstrap for Docker startup.

- Fresh DB  → alembic upgrade head
- Legacy DB (create_all before Alembic) → stamp head, preserve data
- Already migrated → upgrade head
"""
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text

from app.config import settings


def _run_alembic(*args: str) -> None:
    subprocess.check_call(["alembic", "-c", "alembic.ini", *args])


def bootstrap() -> None:
    db_url = settings.DATABASE_URL
    if settings.ENV == "production" and ("localhost" in db_url or "127.0.0.1" in db_url):
        raise RuntimeError(
            "DATABASE_URL points to localhost in production. On Railway, reference your "
            "Postgres service variable (DATABASE_URL=${{Postgres.DATABASE_URL}}) and redeploy."
        )
    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())

    if "alembic_version" in tables:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        if row:
            print(f"Alembic revision {row[0]} — upgrading to head")
            _run_alembic("upgrade", "head")
            return

    if "repositories" in tables:
        print("Legacy schema detected (tables exist, no alembic_version). Stamping head...")
        _run_alembic("stamp", "head")
        return

    print("Fresh database — running initial migration")
    _run_alembic("upgrade", "head")


if __name__ == "__main__":
    try:
        bootstrap()
    except Exception as exc:
        print(f"Migration bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
