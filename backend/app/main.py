"""
AutoDev - Self-Healing Codebase Agent
FastAPI Application Entry Point
"""
import logging

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api.routes import router


def _configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.LOG_FORMAT == "json":
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level, format="%(message)s")


_configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("autodev.startup", version="1.0.0", env=settings.ENV)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # Enum types already exist on container restart — safe to ignore
        log.warning("autodev.db_init_warning", error=str(e))
    yield
    log.info("autodev.shutdown")


app = FastAPI(
    title="AutoDev — Self-Healing Codebase Agent",
    description="Autonomous code analysis, refactoring, and PR automation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "autodev"}
