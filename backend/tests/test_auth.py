"""API authentication tests."""
import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def auth_client(db_session):
    os.environ["API_KEY"] = "test-secret-key"
    get_settings.cache_clear()

    from app.database import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

    os.environ["API_KEY"] = ""
    get_settings.cache_clear()


class TestApiKeyAuth:
    def test_missing_key_returns_401(self, auth_client):
        response = auth_client.get("/api/v1/repos")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_invalid_key_returns_401(self, auth_client):
        response = auth_client.get(
            "/api/v1/repos",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_valid_key_grants_access(self, auth_client):
        response = auth_client.get(
            "/api/v1/repos",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_bearer_token_auth(self, auth_client):
        response = auth_client.get(
            "/api/v1/repos",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert response.status_code == 200

    def test_health_remains_public(self, auth_client):
        response = auth_client.get("/health")
        assert response.status_code == 200
