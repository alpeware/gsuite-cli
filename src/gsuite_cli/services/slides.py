"""Google Slides service: presentation metadata, text extraction, creation."""

from __future__ import annotations

from typing import Any

from gsuite_cli.config import AccountConfig
from gsuite_cli.services.base import execute_api_call, get_service_client


def _get_slides_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "slides", "v1", config)


def get_presentation(
    email: str,
    presentation_id: str,
    config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Retrieve full presentation resource."""
    service = _get_slides_service(email, config)
    req = service.presentations().get(presentationId=presentation_id)
    return execute_api_call(req, "slides", email)


def _extract_text_from_element(element: dict[str, Any]) -> str:
    """Extract all text runs from a page element (shape, table, etc.)."""
    lines: list[str] = []
    shape = element.get("shape")
    if shape:
        text_content = shape.get("text", {})
        for te in text_content.get("textElements", []):
            tr = te.get("textRun")
            if tr and tr.get("content"):
                lines.append(tr["content"])

    table = element.get("table")
    if table:
        for row in table.get("tableRows", []):
            row_texts: list[str] = []
            for cell in row.get("tableCells", []):
                cell_text = cell.get("text", {})
                cell_runs: list[str] = []
                for te in cell_text.get("textElements", []):
                    tr = te.get("textRun")
                    if tr and tr.get("content"):
                        cell_runs.append(tr["content"].strip())
                row_texts.append(" ".join(cell_runs))
            if row_texts:
                lines.append(" | ".join(row_texts) + "\n")

    return "".join(lines)


def read_presentation_text(
    email: str,
    presentation_id: str,
    include_notes: bool = True,
    config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Extract readable text and speaker notes per slide from a presentation."""
    presentation = get_presentation(email, presentation_id, config)
    title = presentation.get("title", "Untitled Presentation")
    slides_data: list[dict[str, Any]] = []

    for index, slide in enumerate(presentation.get("slides", []), start=1):
        slide_id = slide.get("objectId", f"slide_{index}")
        slide_texts: list[str] = []

        for pe in slide.get("pageElements", []):
            extracted = _extract_text_from_element(pe)
            if extracted.strip():
                slide_texts.append(extracted.strip())

        notes_text: str = ""
        if include_notes:
            slide_props = slide.get("slideProperties", {})
            notes_page = slide_props.get("notesPage", {})
            for npe in notes_page.get("pageElements", []):
                extracted = _extract_text_from_element(npe)
                if extracted.strip():
                    notes_text += extracted.strip() + "\n"

        slides_data.append(
            {
                "slide_number": index,
                "slide_id": slide_id,
                "content": slide_texts,
                "speaker_notes": notes_text.strip() if notes_text.strip() else None,
            }
        )

    return {
        "presentation_id": presentation_id,
        "title": title,
        "slide_count": len(slides_data),
        "slides": slides_data,
    }


def create_presentation(
    email: str,
    title: str,
    config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Create a new blank presentation with the specified title."""
    service = _get_slides_service(email, config)
    req = service.presentations().create(body={"title": title})
    return execute_api_call(req, "slides", email)
