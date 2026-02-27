"""
AutoDev - Self-Healing Codebase Agent
FastAPI Application Entry Point
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api.routes import router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("autodev.startup", version="1.0.0", env=settings.ENV)
    Base.metadata.create_all(bind=engine)
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
