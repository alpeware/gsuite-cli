"""CLI commands for managing and listing accounts with tags."""

from __future__ import annotations

from typing import Any

import click

from gsuite_cli.commands.common import GSuiteCommand, GSuiteGroup
from gsuite_cli.config import load_config
from gsuite_cli.formatters import (
    console,
    print_json,
    render_accounts_tags_table,
    render_warning,
)


@click.command(name="list", cls=GSuiteCommand)
@click.option(
    "--tag",
    "-t",
    "--label",
    "-l",
    "filter_tag",
    help="Filter accounts by specific tag or label (e.g. 'work', 'personal')",
)
@click.pass_context
def accounts_list(ctx: click.Context, filter_tag: str | None = None, **kwargs: Any) -> None:
    """List all available accounts with tags, aliases, and default status."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    if kwargs.get("json"):
        is_json = True
    config = load_config()

    if not config.accounts:
        if is_json:
            print_json({"status": "success", "count": 0, "accounts": [], "default_account": None})
        else:
            console.print(
                "[yellow]No accounts registered yet.[/yellow] Run 'gsuite auth add <email>' to get started."
            )
        return

    accounts_data: list[dict[str, Any]] = []
    for email, acc in config.accounts.items():
        tags = list(acc.labels)
        if filter_tag and filter_tag.lower() not in [t.lower() for t in tags]:
            continue
        accounts_data.append(
            {
                "email": email,
                "alias": acc.alias,
                "default": email == config.default_account,
                "tags": tags,
                "labels": tags,
                "scopes_count": len(acc.scopes),
                "token_file": acc.token_file,
            }
        )

    if is_json:
        print_json(
            {
                "status": "success",
                "count": len(accounts_data),
                "default_account": config.default_account,
                "filter_tag": filter_tag,
                "accounts": accounts_data,
            }
        )
    else:
        if not accounts_data and filter_tag:
            all_tags = set()
            for acc in config.accounts.values():
                all_tags.update(acc.labels)
            avail_str = ", ".join(f"#{t}" for t in sorted(all_tags)) if all_tags else "none"
            render_warning(f"No accounts found with tag '{filter_tag}'. Available tags: {avail_str}")
            return

        render_accounts_tags_table(accounts_data, config.default_account, filter_tag=filter_tag)


@click.group(name="accounts", cls=GSuiteGroup, invoke_without_command=True)
@click.option(
    "--tag",
    "-t",
    "--label",
    "-l",
    "filter_tag",
    help="Filter accounts by specific tag or label (e.g. 'work', 'personal')",
)
@click.pass_context
def accounts_group(ctx: click.Context, filter_tag: str | None = None, **kwargs: Any) -> None:
    """List and manage available Google Workspace accounts and tags."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(accounts_list, filter_tag=filter_tag, **kwargs)


# Register list command under accounts_group
accounts_group.add_command(accounts_list)
