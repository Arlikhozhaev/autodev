"""API integration tests (FastAPI TestClient + SQLite)."""
from unittest.mock import MagicMock, patch

from app.models.repo import Repository, RepoStatus


class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "autodev"}


class TestRepos:
    def test_list_repos_empty(self, client):
        response = client.get("/api/v1/repos")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_repo_not_found(self, client):
        response = client.get("/api/v1/repos/nonexistent-id")
        assert response.status_code == 404

    def test_delete_repo_not_found(self, client):
        response = client.delete("/api/v1/repos/nonexistent-id")
        assert response.status_code == 404


class TestAnalyze:
    @patch("app.api.routes.task_full_pipeline.delay")
    def test_analyze_queues_pipeline(self, mock_delay, client, db_session):
        mock_task = MagicMock()
        mock_task.id = "celery-task-abc"
        mock_delay.return_value = mock_task

        response = client.post(
            "/api/v1/analyze",
            json={"repo_url": "https://github.com/acme/demo", "branch": "main"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "celery-task-abc"
        assert data["repo_id"]

        mock_delay.assert_called_once_with(data["repo_id"])

        repo = db_session.query(Repository).filter(Repository.id == data["repo_id"]).first()
        assert repo is not None
        assert repo.owner == "acme"
        assert repo.name == "demo"
        assert repo.task_id == "celery-task-abc"

    @patch("app.api.routes.task_full_pipeline.delay")
    def test_analyze_conflict_when_in_progress(self, mock_delay, client, db_session):
        existing = Repository(
            url="https://github.com/acme/busy",
            owner="acme",
            name="busy",
            status=RepoStatus.ANALYZING,
        )
        db_session.add(existing)
        db_session.commit()

        response = client.post(
            "/api/v1/analyze",
            json={"repo_url": "https://github.com/acme/busy"},
        )
        assert response.status_code == 409
        mock_delay.assert_not_called()


class TestStats:
    def test_stats_empty(self, client):
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_repos"] == 0
        assert data["total_issues"] == 0
        assert data["prs_opened"] == 0
        assert data["validated_refactors"] == 0
