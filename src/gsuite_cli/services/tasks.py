"""Google Tasks API service: tasklists and tasks operations."""

from __future__ import annotations

from typing import Any

from gsuite_cli.config import AccountConfig
from gsuite_cli.services.base import execute_api_call, get_service_client


def _get_tasks_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "tasks", "v1", config)


def list_tasklists(
    email: str,
    limit: int = 20,
    config: AccountConfig | None = None,
) -> list[dict[str, Any]]:
    """List all tasklists for the user."""
    service = _get_tasks_service(email, config)
    req = service.tasklists().list(maxResults=limit)
    res = execute_api_call(req, "tasks", email)
    return res.get("items", [])


def list_tasks(
    email: str,
    tasklist_id: str = "@default",
    show_completed: bool = False,
    show_hidden: bool = False,
    limit: int = 50,
    config: AccountConfig | None = None,
) -> list[dict[str, Any]]:
    """List tasks in a given tasklist."""
    service = _get_tasks_service(email, config)
    req = service.tasks().list(
        tasklist=tasklist_id,
        showCompleted=show_completed,
        showHidden=show_hidden,
        maxResults=limit,
    )
    res = execute_api_call(req, "tasks", email)
    return res.get("items", [])


def create_task(
    email: str,
    title: str,
    tasklist_id: str = "@default",
    notes: str | None = None,
    due: str | None = None,
    config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Create a new task."""
    service = _get_tasks_service(email, config)
    body: dict[str, Any] = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due

    req = service.tasks().insert(tasklist=tasklist_id, body=body)
    return execute_api_call(req, "tasks", email)


def complete_task(
    email: str,
    task_id: str,
    tasklist_id: str = "@default",
    config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Mark a task as completed."""
    service = _get_tasks_service(email, config)
    body = {"status": "completed"}
    req = service.tasks().patch(tasklist=tasklist_id, task=task_id, body=body)
    return execute_api_call(req, "tasks", email)


def delete_task(
    email: str,
    task_id: str,
    tasklist_id: str = "@default",
    config: AccountConfig | None = None,
) -> None:
    """Delete a task."""
    service = _get_tasks_service(email, config)
    req = service.tasks().delete(tasklist=tasklist_id, task=task_id)
    execute_api_call(req, "tasks", email)


def clear_completed_tasks(
    email: str,
    tasklist_id: str = "@default",
    config: AccountConfig | None = None,
) -> None:
    """Clear all completed tasks from a tasklist."""
    service = _get_tasks_service(email, config)
    req = service.tasks().clear(tasklist=tasklist_id)
    execute_api_call(req, "tasks", email)
