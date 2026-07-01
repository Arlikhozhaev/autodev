"""Celery task status API tests."""
from unittest.mock import MagicMock, patch

from app.models.repo import Repository, RepoStatus


class TestTaskStatus:
    @patch("app.services.task_service.AsyncResult")
    def test_task_pending(self, mock_async_result, client, db_session):
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        mock_async_result.return_value = mock_result

        repo = Repository(
            url="https://github.com/acme/demo",
            owner="acme",
            name="demo",
            status=RepoStatus.CLONING,
            task_id="task-xyz",
        )
        db_session.add(repo)
        db_session.commit()

        response = client.get("/api/v1/tasks/task-xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-xyz"
        assert data["status"] == "PENDING"
        assert data["ready"] is False
        assert data["repo_id"] == repo.id

    @patch("app.services.task_service.AsyncResult")
    def test_task_success(self, mock_async_result, client):
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"repo_id": "abc"}
        mock_async_result.return_value = mock_result

        response = client.get("/api/v1/tasks/task-done")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert data["successful"] is True
        assert data["result"] == {"repo_id": "abc"}

    @patch("app.services.task_service.AsyncResult")
    def test_task_failure(self, mock_async_result, client):
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.result = Exception("clone failed")
        mock_async_result.return_value = mock_result

        response = client.get("/api/v1/tasks/task-fail")
        data = response.json()
        assert data["successful"] is False
        assert "clone failed" in data["error"]
