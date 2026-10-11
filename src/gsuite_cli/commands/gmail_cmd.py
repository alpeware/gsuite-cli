"""CLI commands for Gmail (search, read, threads, draft, send, modify)."""

from __future__ import annotations

import sys
from typing import Any

import click

from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import AccountConfig, load_config
from gsuite_cli.formatters import (
    console,
    print_json,
    render_error,
    render_gmail_message,
    render_gmail_search_table,
    render_success,
)
from gsuite_cli.router import execute_across_targets, resolve_command_targets
from gsuite_cli.services.gmail import (
    create_draft,
    get_thread,
    modify_message,
    read_message,
    search_messages,
    send_message,
)


@click.group(name="gmail", cls=GSuiteGroup)
def gmail_group() -> None:
    """Search, read, draft, send, and modify Gmail messages."""


@gmail_group.command(name="search")
@click.argument("query", required=True)
@click.option("--limit", "-n", default=20, help="Maximum number of messages to fetch (default: 20)")
@click.option("--include-spam-trash", is_flag=True, help="Include messages from SPAM and TRASH")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Target all registered accounts")
@click.pass_context
def gmail_search(
    ctx: click.Context,
    query: str,
    limit: int,
    include_spam_trash: bool,
    account: str | None,
    label: str | None,
    all_accounts: bool,
) -> None:
    """Search messages using standard Gmail query syntax."""
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

    def _do_search(email: str, acc: AccountConfig) -> list[dict[str, Any]]:
        return search_messages(
            email,
            query=query,
            limit=limit,
            include_spam_trash=include_spam_trash,
            account_config=acc,
        )

    res = execute_across_targets(targets, _do_search)

    if is_json:
        print_json(res.to_dict())
    else:
        for acc_res in res.results:
            if acc_res.success:
                items = acc_res.data or []
                if not items:
                    console.print(
                        f"[yellow]No messages matched query '{query}' for {acc_res.email}[/yellow]"
                    )
                else:
                    render_gmail_search_table(
                        items, account=acc_res.email if not res.is_single else None
                    )
            else:
                render_error(f"Search failed for {acc_res.email}: {acc_res.error}")


@gmail_group.command(name="read")
@click.argument("message_id", required=True)
@click.option(
    "--format", "format_type", default="markdown", type=click.Choice(["markdown", "full", "body"])
)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def gmail_read(ctx: click.Context, message_id: str, format_type: str, account: str | None) -> None:
    """Read full email body, headers, and attachment information."""
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
        data = read_message(email, message_id, format_type=format_type, account_config=acc)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to read message {message_id}: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, "message": data})
    else:
        render_gmail_message(data)


@gmail_group.command(name="threads")
@click.argument("thread_id", required=True)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def gmail_threads(ctx: click.Context, thread_id: str, account: str | None) -> None:
    """Display an entire thread with all messages in chronological order."""
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
        data = get_thread(email, thread_id, account_config=acc)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to fetch thread {thread_id}: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, "thread": data})
    else:
        msgs = data.get("messages", [])
        console.print(f"[bold cyan]Thread:[/bold cyan] {thread_id} ({len(msgs)} messages)")
        for i, m in enumerate(msgs, start=1):
            console.print(f"\n[bold yellow]--- Message {i}/{len(msgs)} ---[/bold yellow]")
            render_gmail_message(m)


@gmail_group.command(name="draft")
@click.option("--to", required=True, help="Recipient email address")
@click.option("--subject", required=True, help="Email subject line")
@click.option("--body", required=True, help="Email body content")
@click.option("--cc", help="Cc recipients (comma-separated)")
@click.option("--bcc", help="Bcc recipients (comma-separated)")
@click.option(
    "--attach", multiple=True, help="Path to file attachment (can be specified multiple times)"
)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def gmail_draft_create(
    ctx: click.Context,
    to: str,
    subject: str,
    body: str,
    cc: str | None,
    bcc: str | None,
    attach: tuple[str, ...],
    account: str | None,
) -> None:
    """Create a new email draft in Gmail."""
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

    attachments = list(attach) if attach else None
    try:
        res = create_draft(
            email_addr=email,
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to create draft: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_success(
            f"Draft created successfully for '{email}'! Draft ID: [bold]{res.get('draftId')}[/bold]"
        )


@gmail_group.command(name="send")
@click.option("--to", required=True, help="Recipient email address")
@click.option("--subject", required=True, help="Email subject line")
@click.option("--body", required=True, help="Email body content")
@click.option("--cc", help="Cc recipients (comma-separated)")
@click.option("--bcc", help="Bcc recipients (comma-separated)")
@click.option("--reply-to-id", help="Message ID to reply to (sets In-Reply-To and threadId)")
@click.option(
    "--attach", multiple=True, help="Path to file attachment (can be specified multiple times)"
)
@click.option("--confirm", is_flag=True, help="Skip interactive confirmation prompt")
@click.option("--dry-run", is_flag=True, help="Validate and preview email without sending")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def gmail_send(
    ctx: click.Context,
    to: str,
    subject: str,
    body: str,
    cc: str | None,
    bcc: str | None,
    reply_to_id: str | None,
    attach: tuple[str, ...],
    confirm: bool,
    dry_run: bool,
    account: str | None,
) -> None:
    """Send an email immediately."""
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

    attachments = list(attach) if attach else None

    if dry_run:
        preview = {
            "status": "dry_run",
            "from": email,
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "subject": subject,
            "bodyLength": len(body),
            "attachmentsCount": len(attachments) if attachments else 0,
            "replyToId": reply_to_id,
        }
        if is_json:
            print_json(preview)
        else:
            console.print("[yellow][DRY RUN] Email validation succeeded. Not sent:[/yellow]")
            console.print(f"  From: {email}")
            console.print(f"  To:   {to}")
            console.print(f"  Subj: {subject}")
        return

    # Safety check: Require confirmation if interactive
    if not confirm and not is_json:
        if sys.stdin.isatty():
            console.print(f"[bold yellow]About to send email from {email} to {to}:[/bold yellow]")
            console.print(f"Subject: {subject}")
            if not click.confirm("Proceed with sending?"):
                console.print("[yellow]Send cancelled.[/yellow]")
                ctx.exit(0)
        else:
            render_error("Interactive confirmation required or specify --confirm to bypass.")
            ctx.exit(1)

    try:
        res = send_message(
            email_addr=email,
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            reply_to_id=reply_to_id,
            attachments=attachments,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to send email: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_success(f"Email sent successfully from '{email}' to '{to}'! (ID: {res.get('id')})")


@gmail_group.command(name="modify")
@click.argument("message_id", required=True)
@click.option("--add-label", multiple=True, help="Label to add")
@click.option("--remove-label", multiple=True, help="Label to remove")
@click.option("--mark-read", is_flag=True, help="Mark message as read (removes UNREAD label)")
@click.option("--archive", is_flag=True, help="Archive message (removes INBOX label)")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def gmail_modify(
    ctx: click.Context,
    message_id: str,
    add_label: tuple[str, ...],
    remove_label: tuple[str, ...],
    mark_read: bool,
    archive: bool,
    account: str | None,
) -> None:
    """Modify labels on an email (mark read, archive, add/remove tags)."""
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
        res = modify_message(
            email_addr=email,
            message_id=message_id,
            add_labels=list(add_label),
            remove_labels=list(remove_label),
            mark_read=mark_read,
            archive=archive,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to modify message {message_id}: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_success(
            f"Message {message_id} modified successfully. Current labels: {', '.join(res.get('labels', []))}"
        )
