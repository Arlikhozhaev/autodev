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

REQUIRED_TABLES = frozenset(
    {"repositories", "analysis_reports", "code_issues", "refactor_suggestions"}
)


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
        missing = REQUIRED_TABLES - tables
        if missing:
            print(
                "Incomplete schema with alembic_version "
                f"(missing {sorted(missing)}). Resetting revision and migrating..."
            )
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM alembic_version"))
            _run_alembic("upgrade", "head")
            return
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        if row:
            print(f"Alembic revision {row[0]} — upgrading to head")
            _run_alembic("upgrade", "head")
            return

    if REQUIRED_TABLES.intersection(tables) and "alembic_version" not in tables:
        if REQUIRED_TABLES.issubset(tables):
            print("Legacy schema detected (all tables, no alembic_version). Stamping head...")
            _run_alembic("stamp", "head")
        else:
            print(
                "Partial schema detected (missing tables: "
                f"{sorted(REQUIRED_TABLES - tables)}). Running migration..."
            )
            _run_alembic("upgrade", "head")
        return

    print("Fresh database — running initial migration")
    _run_alembic("upgrade", "head")


if __name__ == "__main__":
    try:
        bootstrap()
    except Exception as exc:
        print(f"Migration bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
