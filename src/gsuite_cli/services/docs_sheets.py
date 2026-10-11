"""Google Docs and Sheets services: Markdown extraction, spreadsheet read/append."""

from __future__ import annotations

from typing import Any

from gsuite_cli.config import AccountConfig
from gsuite_cli.services.base import execute_api_call, get_service_client


def _get_docs_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "docs", "v1", config)


def _get_sheets_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "sheets", "v4", config)


def _convert_text_run(element: dict[str, Any]) -> str:
    """Format an individual text run with bold, italic, strikethrough, or markdown link."""
    text_run = element.get("textRun")
    if not text_run:
        return ""

    content = text_run.get("content", "")
    style = text_run.get("textStyle", {})

    # Check for hyperlink
    link = style.get("link", {}).get("url")
    is_bold = style.get("bold")
    is_italic = style.get("italic")
    is_strikethrough = style.get("strikethrough")

    # Strip trailing newline before wrapping markdown delimiters
    has_newline = content.endswith("\n")
    clean = content[:-1] if has_newline else content

    if clean:
        if is_bold:
            clean = f"**{clean}**"
        if is_italic:
            clean = f"*{clean}*"
        if is_strikethrough:
            clean = f"~~{clean}~~"
        if link:
            clean = f"[{clean}]({link})"

    return clean + ("\n" if has_newline else "")


def _convert_paragraph(paragraph: dict[str, Any]) -> str:
    """Convert a Google Docs paragraph into formatted Markdown string."""
    style_name = paragraph.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
    bullet = paragraph.get("bullet")

    text_parts = []
    for elem in paragraph.get("elements", []):
        text_parts.append(_convert_text_run(elem))

    raw_text = "".join(text_parts).rstrip("\n")

    if not raw_text.strip():
        return ""

    if bullet:
        return f"* {raw_text}"

    prefix_map = {
        "TITLE": "# ",
        "SUBTITLE": "## ",
        "HEADING_1": "# ",
        "HEADING_2": "## ",
        "HEADING_3": "### ",
        "HEADING_4": "#### ",
        "HEADING_5": "##### ",
        "HEADING_6": "###### ",
    }
    prefix = prefix_map.get(style_name, "")
    return f"{prefix}{raw_text}"


def _convert_table(table: dict[str, Any]) -> str:
    """Convert a Google Docs table element into a Markdown table."""
    rows = table.get("tableRows", [])
    if not rows:
        return ""

    md_rows = []
    header_col_count = 0

    for i, row in enumerate(rows):
        cells = row.get("tableCells", [])
        if i == 0:
            header_col_count = len(cells)

        cell_texts = []
        for cell in cells:
            cell_content = []
            for elem in cell.get("content", []):
                p = elem.get("paragraph")
                if p:
                    cell_content.append(_convert_paragraph(p).strip())
            cell_texts.append(" ".join(cell_content).replace("\n", " ").strip())

        md_rows.append("| " + " | ".join(cell_texts) + " |")

        # After header row, append separator
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * header_col_count) + " |")

    return "\n".join(md_rows)


def read_doc_as_markdown(
    email_addr: str,
    file_id: str,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Retrieve Google Doc and convert structure and styling into clean Markdown."""
    service = _get_docs_service(email_addr, account_config)
    get_call = service.documents().get(documentId=file_id)
    doc_data = execute_api_call(get_call, "Docs", email_addr)

    title = doc_data.get("title", "Untitled Document")
    body = doc_data.get("body", {})
    structural_elements = body.get("content", [])

    markdown_blocks = [f"# {title}\n"]

    for elem in structural_elements:
        if "paragraph" in elem:
            p_md = _convert_paragraph(elem["paragraph"])
            if p_md:
                markdown_blocks.append(p_md)
        elif "table" in elem:
            t_md = _convert_table(elem["table"])
            if t_md:
                markdown_blocks.append(t_md)

    clean_md = "\n\n".join(markdown_blocks)

    return {
        "id": file_id,
        "title": title,
        "revisionId": doc_data.get("revisionId"),
        "markdown": clean_md,
    }


def read_sheet(
    email_addr: str,
    spreadsheet_id: str,
    range_name: str | None = None,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Read values from a Google Spreadsheet range."""
    service = _get_sheets_service(email_addr, account_config)
    target_range = range_name or "Sheet1!A1:Z100"

    get_call = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=target_range,
        )
    )
    resp = execute_api_call(get_call, "Sheets", email_addr)
    values = resp.get("values", [])

    return {
        "spreadsheetId": spreadsheet_id,
        "range": resp.get("range", target_range),
        "rowCount": len(values),
        "values": values,
    }


def append_sheet(
    email_addr: str,
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Append row(s) to a Google Spreadsheet."""
    service = _get_sheets_service(email_addr, account_config)

    append_call = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
    )
    resp = execute_api_call(append_call, "Sheets", email_addr)
    updates = resp.get("updates", {})

    return {
        "status": "success",
        "action": "appended",
        "spreadsheetId": spreadsheet_id,
        "updatedRange": updates.get("updatedRange"),
        "updatedRows": updates.get("updatedRows"),
        "updatedColumns": updates.get("updatedColumns"),
        "updatedCells": updates.get("updatedCells"),
    }
