"""Tests for Google Tasks service methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gsuite_cli.services.tasks import (
    clear_completed_tasks,
    complete_task,
    create_task,
    delete_task,
    list_tasklists,
    list_tasks,
)


def test_list_tasklists() -> None:
    mock_service = MagicMock()
    mock_service.tasklists().list().execute.return_value = {
        "items": [
            {"id": "tl1", "title": "My Tasks", "updated": "2026-10-11T10:00:00Z"},
            {"id": "tl2", "title": "Work Items", "updated": "2026-10-11T11:00:00Z"},
        ]
    }

    with patch("gsuite_cli.services.tasks._get_tasks_service", return_value=mock_service):
        lists = list_tasklists("test@example.com")
        assert len(lists) == 2
        assert lists[0]["title"] == "My Tasks"
        assert lists[1]["id"] == "tl2"


def test_list_tasks() -> None:
    mock_service = MagicMock()
    mock_service.tasks().list().execute.return_value = {
        "items": [
            {
                "id": "t1",
                "title": "Prepare release notes",
                "status": "needsAction",
                "due": "2026-10-15T00:00:00Z",
                "notes": "Include gsuite-cli details",
            }
        ]
    }

    with patch("gsuite_cli.services.tasks._get_tasks_service", return_value=mock_service):
        tasks = list_tasks("test@example.com", tasklist_id="@default")
        assert len(tasks) == 1
        assert tasks[0]["id"] == "t1"
        assert tasks[0]["title"] == "Prepare release notes"


def test_create_task() -> None:
    mock_service = MagicMock()
    mock_service.tasks().insert().execute.return_value = {
        "id": "t_new",
        "title": "Deploy update",
        "status": "needsAction",
    }

    with patch("gsuite_cli.services.tasks._get_tasks_service", return_value=mock_service):
        res = create_task(
            "test@example.com",
            title="Deploy update",
            notes="Deploy to production cluster",
            due="2026-10-12T00:00:00Z",
        )
        assert res["id"] == "t_new"
        assert res["title"] == "Deploy update"


def test_complete_and_delete_task() -> None:
    mock_service = MagicMock()
    mock_service.tasks().patch().execute.return_value = {
        "id": "t1",
        "status": "completed",
    }

    with patch("gsuite_cli.services.tasks._get_tasks_service", return_value=mock_service):
        done_res = complete_task("test@example.com", task_id="t1")
        assert done_res["status"] == "completed"

        delete_task("test@example.com", task_id="t1")
        mock_service.tasks().delete.assert_called_with(tasklist="@default", task="t1")

        clear_completed_tasks("test@example.com")
        mock_service.tasks().clear.assert_called_with(tasklist="@default")
