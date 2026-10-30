"""CLI commands for Google Slides presentations."""

from __future__ import annotations

import click

from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import load_config
from gsuite_cli.formatters import (
    print_json,
    render_error,
    render_presentation_info,
    render_success,
)
from gsuite_cli.router import resolve_command_targets
from gsuite_cli.services.slides import (
    create_presentation,
    read_presentation_text,
)


@click.group(name="slides", cls=GSuiteGroup)
def slides_group() -> None:
    """Inspect and create Google Slides presentations."""


@slides_group.command(name="info")
@click.argument("presentation_id", required=True)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def slides_info(
    ctx: click.Context,
    presentation_id: str,
    account: str | None,
) -> None:
    """Retrieve metadata and slide overview for a presentation."""
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
        info = read_presentation_text(email, presentation_id=presentation_id, config=acc)
        if is_json:
            print_json({"status": "success", "presentation": info, "account": email})
        else:
            render_presentation_info(info)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to inspect presentation on {email}: {e}")
        ctx.exit(1)


@slides_group.command(name="read")
@click.argument("presentation_id", required=True)
@click.option("--no-notes", is_flag=True, help="Omit speaker notes")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def slides_read(
    ctx: click.Context,
    presentation_id: str,
    no_notes: bool,
    account: str | None,
) -> None:
    """Read all text content and speaker notes from slides."""
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
        data = read_presentation_text(
            email,
            presentation_id=presentation_id,
            include_notes=not no_notes,
            config=acc,
        )
        if is_json:
            print_json({"status": "success", "data": data, "account": email})
        else:
            render_presentation_info(data)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to read presentation on {email}: {e}")
        ctx.exit(1)


@slides_group.command(name="create")
@click.argument("title", required=True)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def slides_create(
    ctx: click.Context,
    title: str,
    account: str | None,
) -> None:
    """Create a new blank presentation."""
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
        created = create_presentation(email, title=title, config=acc)
        pres_id = created.get("presentationId")
        if is_json:
            print_json(
                {
                    "status": "success",
                    "presentation_id": pres_id,
                    "title": title,
                    "account": email,
                }
            )
        else:
            render_success(f"Created presentation '{title}' (ID: {pres_id}) on {email}")
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e), "account": email})
        else:
            render_error(f"Failed to create presentation on {email}: {e}")
        ctx.exit(1)
