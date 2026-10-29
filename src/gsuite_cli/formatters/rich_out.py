"""Rich formatting for human-friendly interactive terminal display."""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


def render_accounts_table(
    accounts: dict[str, Any],
    default_account: str | None = None,
    statuses: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Render a table of configured accounts, aliases, labels, and token health."""
    table = Table(title="Configured Google Accounts", show_lines=True)
    table.add_column("Account (Email)", style="cyan", no_wrap=True)
    table.add_column("Alias", style="magenta")
    table.add_column("Default", justify="center", style="bold yellow")
    table.add_column("Labels", style="green")
    table.add_column("Token Health", style="blue")
    table.add_column("Scopes", style="dim")

    for email, acc in accounts.items():
        is_default = "★ [bold yellow]YES[/bold yellow]" if email == default_account else ""
        alias = acc.alias or ""
        labels_str = ", ".join(acc.labels) if acc.labels else "[dim]none[/dim]"

        status_text = "[green]Ready[/green]"
        if statuses and email in statuses:
            st = statuses[email]
            if not st.get("valid", True):
                status_text = f"[red]{st.get('error', 'Invalid')}[/red]"
            elif st.get("expired", False):
                status_text = "[yellow]Expired (Auto-refresh)[/yellow]"

        scopes_count = len(acc.scopes) if acc.scopes else 0
        scopes_str = f"{scopes_count} scopes"

        table.add_row(email, alias, is_default, labels_str, status_text, scopes_str)

    console.print(table)


def render_accounts_tags_table(
    accounts_data: list[dict[str, Any]],
    default_account: str | None = None,
    filter_tag: str | None = None,
) -> None:
    """Render a clean terminal table of accounts, aliases, default flag, and tags."""
    title = "Available Google Accounts & Tags"
    if filter_tag:
        title += f" (Filtered by tag: [bold green]#{filter_tag}[/bold green])"

    table = Table(title=title, show_lines=True)
    table.add_column("Account (Email)", style="cyan", no_wrap=True)
    table.add_column("Alias", style="magenta")
    table.add_column("Default", justify="center", style="bold yellow")
    table.add_column("Tags", style="green")

    for acc in accounts_data:
        email = acc.get("email", "")
        alias = acc.get("alias") or "[dim]-[/dim]"
        is_default = "★ [bold yellow]YES[/bold yellow]" if acc.get("default", False) else "[dim]-[/dim]"
        tags = acc.get("tags") or acc.get("labels") or []
        tags_str = ", ".join(f"#{t}" for t in tags) if tags else "[dim]none[/dim]"

        table.add_row(email, alias, is_default, tags_str)

    console.print(table)


def render_gmail_search_table(items: list[dict[str, Any]], account: str | None = None) -> None:
    """Render Gmail search results in a compact terminal table."""
    title = f"Gmail Search Results ({len(items)} messages)"
    if account:
        title += f" - [cyan]{account}[/cyan]"

    table = Table(title=title, show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Date", style="blue", no_wrap=True)
    table.add_column("From", style="green", max_width=28, overflow="ellipsis")
    table.add_column("Subject", style="bold white", max_width=45, overflow="ellipsis")
    table.add_column("Snippet / Labels", style="dim")

    for m in items:
        msg_id = m.get("id", "")[:12]
        date_str = m.get("date", "")[:16]
        sender = m.get("from", "")
        subject = m.get("subject", "(No Subject)")
        snippet = m.get("snippet", "")
        labels = ", ".join([lbl for lbl in m.get("labels", []) if not lbl.startswith("CATEGORY_")])
        extra = f"[{labels}] {snippet}" if labels else snippet

        table.add_row(msg_id, date_str, sender, subject, extra)

    console.print(table)


def render_gmail_message(data: dict[str, Any]) -> None:
    """Render full email message with headers, body, and attachment listing."""
    headers_text = Text()
    headers_text.append(f"Subject: {data.get('subject', '(No Subject)')}\n", style="bold white")
    headers_text.append(f"From:    {data.get('from', '')}\n", style="cyan")
    headers_text.append(f"To:      {data.get('to', '')}\n", style="cyan")
    if data.get("cc"):
        headers_text.append(f"Cc:      {data.get('cc')}\n", style="cyan dim")
    headers_text.append(f"Date:    {data.get('date', '')}\n", style="blue")
    headers_text.append(
        f"ID:      {data.get('id', '')} (Thread: {data.get('threadId', '')})\n", style="dim"
    )

    labels = data.get("labels", [])
    if labels:
        headers_text.append(f"Labels:  {', '.join(labels)}\n", style="magenta")

    console.print(Panel(headers_text, title="Email Message", border_style="blue"))

    body = data.get("body", "")
    content_type = data.get("contentType", "text/plain")

    if "markdown" in content_type or body.startswith("#"):
        console.print(Markdown(body))
    else:
        console.print(body)

    attachments = data.get("attachments", [])
    if attachments:
        att_table = Table(title="Attachments", show_lines=False)
        att_table.add_column("Filename", style="bold green")
        att_table.add_column("MIME Type", style="dim")
        att_table.add_column("Size", justify="right")
        for att in attachments:
            att_table.add_row(
                att.get("filename", "unknown"),
                att.get("mimeType", "application/octet-stream"),
                f"{att.get('size', 0):,} bytes",
            )
        console.print(att_table)


def render_calendar_agenda(events: list[dict[str, Any]], title: str = "Upcoming Agenda") -> None:
    """Render calendar agenda list."""
    if not events:
        console.print(f"[yellow]{title}: No events scheduled.[/yellow]")
        return

    table = Table(title=title, show_lines=True)
    table.add_column("Start", style="bold cyan", no_wrap=True)
    table.add_column("End", style="cyan dim", no_wrap=True)
    table.add_column("Event Summary", style="bold white")
    table.add_column("Location / Meet", style="magenta", max_width=30, overflow="ellipsis")
    table.add_column("Attendees", style="dim")

    for ev in events:
        start = ev.get("start", "")
        end = ev.get("end", "")
        summary = ev.get("summary", "(Untitled)")
        location = ev.get("location") or ev.get("meet_link") or ""
        attendees = ", ".join(ev.get("attendees", []))

        table.add_row(start, end, summary, location, attendees)

    console.print(table)


def render_drive_search(files: list[dict[str, Any]], title: str = "Drive Files") -> None:
    """Render list of Drive files in a table."""
    table = Table(title=f"{title} ({len(files)} files)", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name", style="bold white")
    table.add_column("Type", style="cyan")
    table.add_column("Modified", style="blue")
    table.add_column("Size", justify="right", style="dim")

    for f in files:
        f_id = f.get("id", "")
        name = f.get("name", "Untitled")
        mime = f.get("mimeType", "").replace("application/vnd.google-apps.", "google:")
        modified = f.get("modifiedTime", "")[:19]
        size = f"{f.get('size', '-')} bytes" if "size" in f else "-"

        table.add_row(f_id, name, mime, modified, size)

    console.print(table)


def render_sheets_table(rows: list[list[Any]], title: str = "Google Sheet Data") -> None:
    """Render Google Sheets rows in a tabular format."""
    if not rows:
        console.print("[yellow]Empty sheet range.[/yellow]")
        return

    table = Table(title=title, show_lines=True)
    headers = [str(col) for col in rows[0]]
    for h in headers:
        table.add_column(h, style="bold cyan")

    for row in rows[1:]:
        # Pad row to match header count
        str_cells = [str(c) if c is not None else "" for c in row]
        if len(str_cells) < len(headers):
            str_cells.extend([""] * (len(headers) - len(str_cells)))
        table.add_row(*str_cells[: len(headers)])

    console.print(table)


def render_success(message: str) -> None:
    """Render a green success notice."""
    console.print(f"[bold green]✔[/bold green] {message}")


def render_warning(message: str) -> None:
    """Render a yellow warning notice."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def render_status(message: str, status: str = "info") -> None:
    """Render an informational status message."""
    color = "green" if status == "success" else "yellow" if status == "warning" else "cyan"
    console.print(f"[{color}]•[/{color}] {message}")


def render_error(message: str, details: dict[str, Any] | None = None) -> None:
    """Render a red error notice with optional details."""
    err_console.print(f"[bold red]✖ Error:[/bold red] {message}")
    if details:
        for k, v in details.items():
            err_console.print(f"  [dim]{k}:[/dim] {v}")


def render_tasklists(tasklists: list[dict[str, Any]], account: str | None = None) -> None:
    """Render a table of Google Task lists."""
    title = f"Task Lists ({len(tasklists)})"
    if account:
        title += f" - [cyan]{account}[/cyan]"

    table = Table(title=title, show_lines=False)
    table.add_column("List ID", style="dim")
    table.add_column("Title", style="bold white")
    table.add_column("Updated", style="blue")

    for tl in tasklists:
        table.add_row(tl.get("id", ""), tl.get("title", "Untitled"), tl.get("updated", "")[:19])

    console.print(table)


def render_tasks_list(tasks: list[dict[str, Any]], title: str = "Tasks") -> None:
    """Render a list of tasks with completion status, due date, and notes."""
    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title=title, show_lines=False)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Title", style="bold white")
    table.add_column("Due Date", style="yellow")
    table.add_column("Notes", style="dim")

    for t in tasks:
        is_completed = t.get("status") == "completed"
        status_icon = "[green]✔ Done[/green]" if is_completed else "[yellow]○ Pending[/yellow]"
        task_id = t.get("id", "")[:16]
        task_title = t.get("title", "(No title)")
        due = t.get("due", "")[:10] if t.get("due") else "-"
        notes = (t.get("notes", "") or "").replace("\n", " ")[:40]
        table.add_row(status_icon, task_id, task_title, due, notes)

    console.print(table)


def render_presentation_info(info: dict[str, Any]) -> None:
    """Render summary and slide listing for a Google Slides presentation."""
    title = info.get("title", "Untitled Presentation")
    slide_count = info.get("slide_count", 0)
    pres_id = info.get("presentation_id", "")

    header = Text()
    header.append(f"Presentation: {title}\n", style="bold white")
    header.append(f"ID:           {pres_id}\n", style="dim")
    header.append(f"Total Slides: {slide_count}\n", style="cyan")

    console.print(Panel(header, title="Google Slides", border_style="yellow"))

    for s in info.get("slides", []):
        s_num = s.get("slide_number")
        s_id = s.get("slide_id")
        content = s.get("content", [])
        speaker_notes = s.get("speaker_notes")

        slide_text = Text()
        slide_text.append(f"Slide {s_num} (ID: {s_id})\n", style="bold cyan")
        if content:
            for block in content:
                slide_text.append(f"  • {block}\n", style="white")
        else:
            slide_text.append("  [dim](No text elements)[/dim]\n")

        if speaker_notes:
            slide_text.append(f"\n  [italic dim]Speaker Notes:[/italic dim] {speaker_notes}\n")

        console.print(Panel(slide_text, border_style="dim"))

