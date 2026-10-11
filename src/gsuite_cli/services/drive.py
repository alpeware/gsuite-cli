"""Google Drive service implementation for file search and export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from googleapiclient.http import MediaIoBaseDownload

from gsuite_cli.config import AccountConfig
from gsuite_cli.exceptions import ServiceError
from gsuite_cli.services.base import execute_api_call, get_service_client

EXPORT_MIME_MAP = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "markdown": "text/markdown",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _get_drive_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "drive", "v3", config)


def search_files(
    email_addr: str,
    query: str | None = None,
    mime_type: str | None = None,
    limit: int = 20,
    account_config: AccountConfig | None = None,
) -> list[dict[str, Any]]:
    """Search files in Google Drive."""
    service = _get_drive_service(email_addr, account_config)

    clauses = ["trashed = false"]
    if mime_type:
        clauses.append(f"mimeType = '{mime_type}'")
    if query:
        clauses.append(f"name contains '{query}' or fullText contains '{query}'")

    q_str = " and ".join(clauses)

    list_call = service.files().list(
        q=q_str,
        pageSize=limit,
        fields="files(id, name, mimeType, modifiedTime, size, webViewLink)",
        orderBy="modifiedTime desc",
    )
    resp = execute_api_call(list_call, "Drive", email_addr)
    return resp.get("files", [])


def export_file(
    email_addr: str,
    file_id: str,
    export_format: str,
    output_path: str,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Export a Google Workspace document/sheet/slide to a local file."""
    service = _get_drive_service(email_addr, account_config)
    fmt = export_format.lower().lstrip(".")
    target_mime = EXPORT_MIME_MAP.get(fmt, fmt)

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Check if file is a native Google Doc/Sheet requiring export or binary
        get_meta = service.files().get(fileId=file_id, fields="id, name, mimeType")
        meta = execute_api_call(get_meta, "Drive", email_addr)
        orig_mime = meta.get("mimeType", "")

        if orig_mime.startswith("application/vnd.google-apps."):
            request = service.files().export_media(fileId=file_id, mimeType=target_mime)
        else:
            request = service.files().get_media(fileId=file_id)

        with open(out_file, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return {
            "status": "success",
            "action": "exported",
            "fileId": file_id,
            "filename": meta.get("name"),
            "savedTo": str(out_file),
            "sizeBytes": out_file.stat().st_size,
        }
    except Exception as e:
        raise ServiceError(
            f"Failed to export file {file_id}: {e}", service="Drive", account=email_addr
        )
