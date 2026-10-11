"""Gmail service implementation for search, read, thread, draft, send, and modify."""

from __future__ import annotations

import base64
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from gsuite_cli.config import AccountConfig
from gsuite_cli.exceptions import ServiceError
from gsuite_cli.services.base import execute_api_call, get_service_client


def _get_gmail_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "gmail", "v1", config)


def _parse_headers(headers: list[dict[str, str]]) -> dict[str, str]:
    """Parse list of header dicts into normalized dictionary."""
    parsed: dict[str, str] = {}
    for h in headers:
        name = h.get("name", "").lower()
        parsed[name] = h.get("value", "")
    return parsed


def _decode_body_part(part: dict[str, Any]) -> str:
    """Decode base64url data from message part body."""
    body_data = part.get("body", {}).get("data", "")
    if not body_data:
        return ""
    try:
        decoded_bytes = base64.urlsafe_b64decode(body_data.encode("ASCII"))
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body_and_attachments(payload: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    """Recursively extract plain text or HTML body, and attachment metadata."""
    plain_text = ""
    html_text = ""
    attachments: list[dict[str, Any]] = []

    def _traverse(part: dict[str, Any]) -> None:
        nonlocal plain_text, html_text
        mime_type = part.get("mimeType", "")
        filename = part.get("filename", "")
        body = part.get("body", {})

        if filename and body.get("attachmentId"):
            attachments.append(
                {
                    "attachmentId": body.get("attachmentId"),
                    "filename": filename,
                    "mimeType": mime_type,
                    "size": body.get("size", 0),
                }
            )
            return

        if mime_type == "text/plain" and not plain_text:
            plain_text = _decode_body_part(part)
        elif mime_type == "text/html" and not html_text:
            html_text = _decode_body_part(part)

        parts = part.get("parts", [])
        for sub_part in parts:
            _traverse(sub_part)

    _traverse(payload)

    body = plain_text or html_text
    content_type = "text/plain" if plain_text else "text/html"
    return body, content_type, attachments


def search_messages(
    email_addr: str,
    query: str,
    limit: int = 20,
    include_spam_trash: bool = False,
    account_config: AccountConfig | None = None,
) -> list[dict[str, Any]]:
    """Search Gmail messages matching standard query syntax."""
    service = _get_gmail_service(email_addr, account_config)
    list_call = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=limit,
            includeSpamTrash=include_spam_trash,
        )
    )
    resp = execute_api_call(list_call, "Gmail", email_addr)
    message_stubs = resp.get("messages", [])

    if not message_stubs:
        return []

    results: list[dict[str, Any]] = []
    # Fetch lightweight metadata for each message
    for stub in message_stubs[:limit]:
        msg_id = stub["id"]
        get_call = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date"],
            )
        )
        msg_data = execute_api_call(get_call, "Gmail", email_addr)
        headers = _parse_headers(msg_data.get("payload", {}).get("headers", []))

        results.append(
            {
                "id": msg_data.get("id"),
                "threadId": msg_data.get("threadId"),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", "(No Subject)"),
                "date": headers.get("date", ""),
                "snippet": msg_data.get("snippet", ""),
                "labels": msg_data.get("labelIds", []),
            }
        )

    return results


def read_message(
    email_addr: str,
    message_id: str,
    format_type: str = "full",
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Read full message headers, body, and attachment metadata."""
    service = _get_gmail_service(email_addr, account_config)
    get_call = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full",
        )
    )
    msg_data = execute_api_call(get_call, "Gmail", email_addr)

    payload = msg_data.get("payload", {})
    headers = _parse_headers(payload.get("headers", []))
    body, content_type, attachments = _extract_body_and_attachments(payload)

    return {
        "id": msg_data.get("id"),
        "threadId": msg_data.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", "(No Subject)"),
        "date": headers.get("date", ""),
        "labels": msg_data.get("labelIds", []),
        "snippet": msg_data.get("snippet", ""),
        "contentType": content_type,
        "body": body,
        "attachments": attachments,
    }


def get_thread(
    email_addr: str,
    thread_id: str,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Retrieve full thread including all constituent messages in chronological order."""
    service = _get_gmail_service(email_addr, account_config)
    get_call = service.users().threads().get(userId="me", id=thread_id, format="full")
    thread_data = execute_api_call(get_call, "Gmail", email_addr)

    messages = []
    for raw_msg in thread_data.get("messages", []):
        payload = raw_msg.get("payload", {})
        headers = _parse_headers(payload.get("headers", []))
        body, content_type, attachments = _extract_body_and_attachments(payload)
        messages.append(
            {
                "id": raw_msg.get("id"),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "date": headers.get("date", ""),
                "subject": headers.get("subject", "(No Subject)"),
                "labels": raw_msg.get("labelIds", []),
                "body": body,
                "contentType": content_type,
                "attachments": attachments,
            }
        )

    return {
        "threadId": thread_id,
        "messageCount": len(messages),
        "messages": messages,
    }


def _build_mime_message(
    sender: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachments: list[str] | None = None,
) -> EmailMessage:
    """Construct standard Python EmailMessage with optional file attachments."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    msg.set_content(body)

    if attachments:
        for file_path in attachments:
            path = Path(file_path).expanduser().resolve()
            if not path.is_file():
                raise ServiceError(f"Attachment file not found: {file_path}")

            ctype, encoding = mimetypes.guess_type(str(path))
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            with open(path, "rb") as fp:
                file_data = fp.read()

            msg.add_attachment(
                file_data,
                maintype=maintype,
                subtype=subtype,
                filename=path.name,
            )

    return msg


def create_draft(
    email_addr: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachments: list[str] | None = None,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Create a draft email in the user's Gmail mailbox."""
    service = _get_gmail_service(email_addr, account_config)
    mime_msg = _build_mime_message(email_addr, to, subject, body, cc, bcc, attachments)
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("ASCII")

    create_call = (
        service.users()
        .drafts()
        .create(
            userId="me",
            body={"message": {"raw": raw}},
        )
    )
    resp = execute_api_call(create_call, "Gmail", email_addr)
    return {
        "status": "success",
        "action": "draft_created",
        "draftId": resp.get("id"),
        "messageId": resp.get("message", {}).get("id"),
        "to": to,
        "subject": subject,
    }


def send_message(
    email_addr: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    reply_to_id: str | None = None,
    attachments: list[str] | None = None,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Send an email immediately via Gmail API."""
    service = _get_gmail_service(email_addr, account_config)
    mime_msg = _build_mime_message(email_addr, to, subject, body, cc, bcc, attachments)

    body_payload: dict[str, Any] = {}
    if reply_to_id:
        # Fetch threadId and original Message-ID for in-reply-to headers
        orig = read_message(email_addr, reply_to_id, account_config=account_config)
        mime_msg["In-Reply-To"] = reply_to_id
        mime_msg["References"] = reply_to_id
        body_payload["threadId"] = orig.get("threadId")

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("ASCII")
    body_payload["raw"] = raw

    send_call = service.users().messages().send(userId="me", body=body_payload)
    resp = execute_api_call(send_call, "Gmail", email_addr)

    return {
        "status": "success",
        "action": "sent",
        "id": resp.get("id"),
        "threadId": resp.get("threadId"),
        "to": to,
        "subject": subject,
    }


def modify_message(
    email_addr: str,
    message_id: str,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
    mark_read: bool = False,
    archive: bool = False,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Modify labels on a Gmail message (e.g. mark read, archive)."""
    service = _get_gmail_service(email_addr, account_config)
    add_set = set(add_labels or [])
    rem_set = set(remove_labels or [])

    if mark_read:
        rem_set.add("UNREAD")
    if archive:
        rem_set.add("INBOX")

    mod_call = (
        service.users()
        .messages()
        .modify(
            userId="me",
            id=message_id,
            body={
                "addLabelIds": list(add_set),
                "removeLabelIds": list(rem_set),
            },
        )
    )
    resp = execute_api_call(mod_call, "Gmail", email_addr)
    return {
        "status": "success",
        "action": "modified",
        "id": resp.get("id"),
        "labels": resp.get("labelIds", []),
    }
