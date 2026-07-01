"""
FastAPI dependencies — authentication and shared guards.
"""
from typing import Optional

from fastapi import Header, HTTPException, status

from app.config import get_settings


def _extract_api_key(
    x_api_key: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    """
  Validate API key when API_KEY is configured.
  Development: leave API_KEY empty to disable auth.
  Production: set API_KEY in environment — all /api/v1/* routes require it.
    """
    settings = get_settings()
    if not settings.API_KEY:
        return

    provided = _extract_api_key(x_api_key, authorization)
    if not provided or provided != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass X-API-Key header or Authorization: Bearer <key>.",
        )
