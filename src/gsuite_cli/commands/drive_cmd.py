"""CLI commands for Google Drive, Docs, and Sheets."""

from __future__ import annotations

import json
from typing import Any

import click

from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import AccountConfig, load_config
from gsuite_cli.formatters import (
    console,
    print_json,
    render_drive_search,
    render_error,
    render_sheets_table,
    render_success,
)
from gsuite_cli.router import execute_across_targets, resolve_command_targets
from gsuite_cli.services.docs_sheets import (
    append_sheet,
    read_doc_as_markdown,
    read_sheet,
)
from gsuite_cli.services.drive import export_file, search_files


@click.group(name="drive", cls=GSuiteGroup)
def drive_group() -> None:
    """Search Drive files and export documents."""


@drive_group.command(name="search")
@click.argument("query", required=False, default="")
@click.option("--mime-type", help="Filter by MIME type (e.g. 'application/pdf')")
@click.option("--limit", "-n", default=20, help="Maximum number of files (default: 20)")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Target all registered accounts")
@click.pass_context
def drive_search(
    ctx: click.Context,
    query: str,
    mime_type: str | None,
    limit: int,
    account: str | None,
    label: str | None,
    all_accounts: bool,
) -> None:
    """Search files in Google Drive."""
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
        return search_files(
            email,
            query=query if query else None,
            mime_type=mime_type,
            limit=limit,
            account_config=acc,
        )

    res = execute_across_targets(targets, _do_search)

    if is_json:
        print_json(res.to_dict())
    else:
        for acc_res in res.results:
            if acc_res.success:
                files = acc_res.data or []
                title = f"Files for {acc_res.email}" if not res.is_single else "Drive Files"
                render_drive_search(files, title=title)
            else:
                render_error(f"Failed to search Drive for {acc_res.email}: {acc_res.error}")


@drive_group.command(name="export")
@click.argument("file_id", required=True)
@click.option(
    "--format",
    "export_format",
    default="pdf",
    help="Export format: pdf, txt, markdown, csv, xlsx, docx",
)
@click.option("--output", "-o", required=True, help="Destination local file path")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def drive_export(
    ctx: click.Context, file_id: str, export_format: str, output: str, account: str | None
) -> None:
    """Export a Google Workspace document/sheet/slide to a local file."""
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
        res = export_file(
            email_addr=email,
            file_id=file_id,
            export_format=export_format,
            output_path=output,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Export failed: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_success(
            f"File exported successfully to '{res.get('savedTo')}' ({res.get('sizeBytes'):,} bytes)!"
        )


# Standalone docs group
@click.group(name="docs", cls=GSuiteGroup)
def docs_group() -> None:
    """Inspect and read Google Docs."""


@docs_group.command(name="read")
@click.argument("file_id", required=True)
@click.option(
    "--markdown", is_flag=True, default=True, help="Render document as Markdown (default)"
)
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def docs_read(ctx: click.Context, file_id: str, markdown: bool, account: str | None) -> None:
    """Read Google Doc and extract clean Markdown content."""
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
        res = read_doc_as_markdown(email_addr=email, file_id=file_id, account_config=acc)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to read document: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        from rich.markdown import Markdown

        console.print(Markdown(res.get("markdown", "")))


# Standalone sheets group
@click.group(name="sheets", cls=GSuiteGroup)
def sheets_group() -> None:
    """Read and append to Google Sheets."""


@sheets_group.command(name="read")
@click.argument("spreadsheet_id", required=True)
@click.option("--range", "range_name", help="A1 notation range (e.g. 'Sheet1!A1:D20')")
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def sheets_read(
    ctx: click.Context, spreadsheet_id: str, range_name: str | None, account: str | None
) -> None:
    """Read tabular data from a Google Spreadsheet range."""
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
        res = read_sheet(
            email_addr=email,
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to read spreadsheet: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_sheets_table(
            res.get("values", []), title=f"Spreadsheet: {spreadsheet_id} ({res.get('range')})"
        )


@sheets_group.command(name="append")
@click.argument("spreadsheet_id", required=True)
@click.option("--range", "range_name", required=True, help="Target range (e.g. 'Sheet1!A1')")
@click.option("--values", required=True, help='JSON array of rows (e.g. \'[["col1", "col2"]]\')')
@click.option("--account", "-a", help="Target account (defaults to default_account)")
@click.pass_context
def sheets_append(
    ctx: click.Context, spreadsheet_id: str, range_name: str, values: str, account: str | None
) -> None:
    """Append row(s) to a Google Spreadsheet."""
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
        parsed_values = json.loads(values)
        if not isinstance(parsed_values, list):
            raise ValueError('Values must be a JSON array of rows, e.g. \'[["a", "b"]]\'')
        if parsed_values and not isinstance(parsed_values[0], list):
            # If user provided a single row '["a", "b"]', wrap it into a list of rows
            parsed_values = [parsed_values]
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": f"Invalid JSON values: {e}"})
        else:
            render_error(f"Invalid JSON values: {e}")
        ctx.exit(1)

    try:
        res = append_sheet(
            email_addr=email,
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            values=parsed_values,
            account_config=acc,
        )
    except Exception as e:
        if is_json:
            print_json({"status": "error", "account": email, "message": str(e)})
        else:
            render_error(f"Failed to append to spreadsheet: {e}")
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", "account": email, **res})
    else:
        render_success(
            f"Appended {res.get('updatedRows', 1)} row(s) to {spreadsheet_id} at {res.get('updatedRange')}"
        )
