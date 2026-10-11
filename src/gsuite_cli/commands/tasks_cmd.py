"""CLI commands for Google Tasks."""

from __future__ import annotations

from typing import Any

import click

from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import AccountConfig, load_config
from gsuite_cli.formatters import (
    print_json,
    render_error,
    render_status,
    render_success,
    render_tasklists,
    render_tasks_list,
)
from gsuite_cli.router import execute_across_targets, resolve_command_targets
from gsuite_cli.services.tasks import (
    clear_completed_tasks,
    complete_task,
    create_task,
    delete_task,
    list_tasklists,
    list_tasks,
)


@click.group(name="tasks", cls=GSuiteGroup)
def tasks_group() -> None:
    """Manage and inspect Google Tasks and Task Lists."""


@tasks_group.command(name="lists")
@click.option("--limit", "-n", default=20, help="Maximum number of task lists (default: 20)")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Target all registered accounts")
@click.pass_context
def tasks_lists(
    ctx: click.Context,
    limit: int,
    account: str | None,
    label: str | None,
    all_accounts: bool,
) -> None:
    """List all Google Task lists."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = resolve_command_targets(
            config, account=account, label=label, all_accounts=all_accounts
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    def _do_list(email: str, acc: AccountConfig) -> list[dict[str, Any]]:
        return list_tasklists(email, limit=limit, config=acc)

    res = execute_across_targets(targets, _do_list)

    if is_json:
        print_json(res.to_dict())
    else:
        for acc_res in res.results:
            if acc_res.success:
                tasklists = acc_res.data or []
                render_tasklists(tasklists, account=acc_res.email if not res.is_single else None)
            else:
                render_error(f"Failed to list tasklists for {acc_res.email}: {acc_res.error}")


@tasks_group.command(name="list")
@click.argument("tasklist_id", required=False, default="@default")
@click.option("--all-tasks", is_flag=True, help="Show both pending and completed tasks")
@click.option("--limit", "-n", default=50, help="Maximum number of tasks (default: 50)")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Target all registered accounts")
@click.pass_context
def tasks_list(
    ctx: click.Context,
    tasklist_id: str,
    all_tasks: bool,
    limit: int,
    account: str | None,
    label: str | None,
    all_accounts: bool,
) -> None:
    """List tasks in a task list (@default by default)."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = resolve_command_targets(
            config, account=account, label=label, all_accounts=all_accounts
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    def _do_list(email: str, acc: AccountConfig) -> list[dict[str, Any]]:
        return list_tasks(
            email,
            tasklist_id=tasklist_id,
            show_completed=all_tasks,
            show_hidden=all_tasks,
            limit=limit,
            config=acc,
        )

    res = execute_across_targets(targets, _do_list)

    if is_json:
        print_json(res.to_dict())
    else:
        for acc_res in res.results:
            if acc_res.success:
                items = acc_res.data or []
                title = f"Tasks for {acc_res.email}" if not res.is_single else "Tasks"
                render_tasks_list(items, title=title)
            else:
                render_error(f"Failed to list tasks for {acc_res.email}: {acc_res.error}")


@tasks_group.command(name="add")
@click.argument("title", required=True)
@click.option("--tasklist", default="@default", help="Target task list ID (default: @default)")
@click.option("--notes", help="Detailed description or notes for the task")
@click.option("--due", help="Due date in RFC 3339 format (e.g. 2026-10-15T00:00:00Z)")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def tasks_add(
    ctx: click.Context,
    title: str,
    tasklist: str,
    notes: str | None,
    due: str | None,
    account: str | None,
) -> None:
    """Add a new task."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = resolve_command_targets(config, account=account)
        email, acc = targets[0]
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    try:
        created = create_task(
            email,
            title=title,
            tasklist_id=tasklist,
            notes=notes,
            due=due,
            config=acc,
        )
        if is_json:
            print_json({"status": "success", "task": created, "account": email})
        else:
            render_success(f"Task created on {email}: '{title}' (ID: {created.get('id')})")
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to create task on {email}: {e}")
        ctx.exit(1)


@tasks_group.command(name="done")
@click.argument("task_id", required=True)
@click.option("--tasklist", default="@default", help="Task list ID (default: @default)")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def tasks_done(
    ctx: click.Context,
    task_id: str,
    tasklist: str,
    account: str | None,
) -> None:
    """Mark a task as completed."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = resolve_command_targets(config, account=account)
        email, acc = targets[0]
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    try:
        res = complete_task(email, task_id=task_id, tasklist_id=tasklist, config=acc)
        if is_json:
            print_json({"status": "success", "task": res, "account": email})
        else:
            render_success(f"Task {task_id} on {email} marked as completed.")
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to complete task on {email}: {e}")
        ctx.exit(1)


@tasks_group.command(name="delete")
@click.argument("task_id", required=True)
@click.option("--tasklist", default="@default", help="Task list ID (default: @default)")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def tasks_delete(
    ctx: click.Context,
    task_id: str,
    tasklist: str,
    account: str | None,
) -> None:
    """Delete a task."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = resolve_command_targets(config, account=account)
        email, acc = targets[0]
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    try:
        delete_task(email, task_id=task_id, tasklist_id=tasklist, config=acc)
        if is_json:
            print_json({"status": "success", "deleted": task_id, "account": email})
        else:
            render_success(f"Task {task_id} deleted on {email}.")
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to delete task on {email}: {e}")
        ctx.exit(1)


@tasks_group.command(name="clear")
@click.option("--tasklist", default="@default", help="Task list ID (default: @default)")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def tasks_clear(
    ctx: click.Context,
    tasklist: str,
    account: str | None,
) -> None:
    """Clear all completed tasks from a tasklist."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = resolve_command_targets(config, account=account)
        email, acc = targets[0]
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    try:
        clear_completed_tasks(email, tasklist_id=tasklist, config=acc)
        if is_json:
            print_json({"status": "success", "cleared": tasklist, "account": email})
        else:
            render_success(f"Cleared completed tasks in list {tasklist} on {email}.")
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to clear tasks on {email}: {e}")
        ctx.exit(1)
