"""CLI commands for Google Calendar (agenda, events, freebusy, create)."""

from __future__ import annotations

from typing import Any

import click

from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import AccountConfig, load_config
from gsuite_cli.formatters import (
    console,
    print_json,
    render_calendar_agenda,
    render_error,
    render_success,
)
from gsuite_cli.router import execute_across_targets, resolve_command_targets
from gsuite_cli.services.calendar import (
    create_event,
    get_agenda,
    list_events,
    query_freebusy,
)


@click.group(name="calendar", cls=GSuiteGroup)
def calendar_group() -> None:
    """Manage and inspect Google Calendar events and schedules."""


@calendar_group.command(name="agenda")
@click.option("--days", "-d", default=1, help="Number of days to include (default: 1)")
@click.option("--today", is_flag=True, help="Limit to today's events only")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Target all registered accounts")
@click.pass_context
def calendar_agenda(
    ctx: click.Context,
    days: int,
    today: bool,
    account: str | None,
    label: str | None,
    all_accounts: bool,
) -> None:
    """Show upcoming agenda for today or next N days."""
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

    def _do_agenda(email: str, acc: AccountConfig) -> list[dict[str, Any]]:
        return get_agenda(email, days=days, today=today, account_config=acc)

    res = execute_across_targets(targets, _do_agenda)

    if is_json:
        print_json(res.to_dict())
    else:
        for acc_res in res.results:
            if acc_res.success:
                events = acc_res.data or []
                title = f"Agenda for {acc_res.email}" if not res.is_single else "Upcoming Agenda"
                render_calendar_agenda(events, title=title)
            else:
                render_error(f"Failed to fetch agenda for {acc_res.email}: {acc_res.error}")


@calendar_group.command(name="events")
@click.option("--start", help="Start time in ISO format (e.g. 2026-10-12T09:00:00Z)")
@click.option("--end", help="End time in ISO format (e.g. 2026-10-12T17:00:00Z)")
@click.option("--query", "-q", help="Search query string")
@click.option("--limit", "-n", default=20, help="Maximum number of events to return (default: 20)")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Target all registered accounts")
@click.pass_context
def calendar_events(
    ctx: click.Context,
    start: str | None,
    end: str | None,
    query: str | None,
    limit: int,
    account: str | None,
    label: str | None,
    all_accounts: bool,
) -> None:
    """Search and filter calendar events across a date range."""
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
        return list_events(
            email,
            start_iso=start,
            end_iso=end,
            query=query,
            limit=limit,
            account_config=acc,
        )

    res = execute_across_targets(targets, _do_list)

    if is_json:
        print_json(res.to_dict())
    else:
        for acc_res in res.results:
            if acc_res.success:
                events = acc_res.data or []
                title = f"Events for {acc_res.email}" if not res.is_single else "Calendar Events"
                render_calendar_agenda(events, title=title)
            else:
                render_error(f"Failed to fetch events for {acc_res.email}: {acc_res.error}")


@calendar_group.command(name="freebusy")
@click.option("--emails", required=True, help="Comma-separated emails to check availability for")
@click.option("--start", required=True, help="Start time in ISO format (e.g. 2026-10-12T09:00:00Z)")
@click.option("--end", required=True, help="End time in ISO format (e.g. 2026-10-12T17:00:00Z)")
@click.option("--account", "-a", help="Account executing the query (defaults to default_account)")
@click.pass_context
def calendar_freebusy(
    ctx: click.Context,
    emails: str,
    start: str,
    end: str,
    account: str | None,
) -> None:
    """Query free/busy schedule across one or more participants."""
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

    email_list = [e.strip() for e in emails.split(",") if e.strip()]
    try:
        res = query_freebusy(
            email, emails=email_list, start_iso=start, end_iso=end, account_config=acc
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Free/busy query failed: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        console.print(f"[bold cyan]Free/Busy Availability ({start} to {end}):[/bold cyan]")
        for cal_id, blocks in res.get("calendars", {}).items():
            if not blocks:
                console.print(f"  [green]• {cal_id}:[/green] Free (no busy intervals)")
            else:
                console.print(f"  [yellow]• {cal_id}:[/yellow] {len(blocks)} busy block(s)")
                for b in blocks:
                    console.print(f"      {b.get('start')} -> {b.get('end')}")


@calendar_group.command(name="create")
@click.option("--summary", required=True, help="Event title/summary")
@click.option(
    "--start", required=True, help="Start time in ISO format (e.g. 2026-10-12T14:00:00-05:00)"
)
@click.option(
    "--end", required=True, help="End time in ISO format (e.g. 2026-10-12T15:00:00-05:00)"
)
@click.option("--attendees", help="Comma-separated attendee emails")
@click.option("--description", help="Event description notes")
@click.option("--location", help="Event physical location or URL")
@click.option("--meet", is_flag=True, default=False, help="Add Google Meet video conferencing")
@click.option(
    "--send-updates",
    type=click.Choice(["all", "none", "external_only"]),
    default="all",
    help="Whether to send notifications about the creation of the new event",
)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def calendar_create(
    ctx: click.Context,
    summary: str,
    start: str,
    end: str,
    attendees: str | None,
    description: str | None,
    location: str | None,
    meet: bool,
    send_updates: str,
    account: str | None,
) -> None:
    """Create a new event on the primary calendar."""
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

    att_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else None

    try:
        res = create_event(
            email_addr=email,
            summary=summary,
            start_iso=start,
            end_iso=end,
            attendees=att_list,
            description=description,
            location=location,
            meet=meet,
            send_updates=send_updates,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to create event: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_success(f"Calendar event '{summary}' created successfully for '{email}'!")
        console.print(f"  Start: {res.get('start')}")
        console.print(f"  End:   {res.get('end')}")
        if res.get("meet_link"):
            console.print(f"  Meet:  {res.get('meet_link')}")
        if res.get("htmlLink"):
            console.print(f"  Link:  {res.get('htmlLink')}")
