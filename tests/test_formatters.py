"""Tests for JSON and Rich formatters."""

from __future__ import annotations

import datetime
from io import StringIO
from unittest.mock import patch

from pydantic import BaseModel

from gsuite_cli.config import AccountConfig
from gsuite_cli.formatters.json_out import json_serial_fallback, print_json
from gsuite_cli.formatters.rich_out import (
    render_accounts_table,
    render_calendar_agenda,
    render_drive_search,
    render_gmail_message,
    render_gmail_search_table,
    render_sheets_table,
)


class DummyModel(BaseModel):
    name: str
    count: int


def test_json_serial_fallback() -> None:
    dt = datetime.datetime(2026, 10, 11, 12, 0, 0)
    assert json_serial_fallback(dt) == "2026-10-11T12:00:00"

    m = DummyModel(name="test", count=42)
    assert json_serial_fallback(m) == {"name": "test", "count": 42}

    s = {"a", "b"}
    assert isinstance(json_serial_fallback(s), list)

    b = b"hello"
    assert json_serial_fallback(b) == "hello"


def test_print_json_captures_valid_json() -> None:
    data = {"status": "success", "count": 2, "items": ["a", "b"]}
    with patch("sys.stdout", new_callable=StringIO) as mock_out:
        print_json(data)
        out_str = mock_out.getvalue()
        assert '"status": "success"' in out_str
        assert '"count": 2' in out_str


def test_rich_renderers_do_not_crash() -> None:
    # Verify rich renderers execute without error
    accounts = {"user@gmail.com": AccountConfig(alias="me", labels=["personal"], scopes=["scope1"])}
    render_accounts_table(accounts, default_account="user@gmail.com")

    messages = [
        {
            "id": "123",
            "date": "2026-10-11",
            "from": "sender@example.com",
            "subject": "Hello",
            "snippet": "Preview...",
            "labels": ["INBOX"],
        }
    ]
    render_gmail_search_table(messages)

    msg = {
        "id": "123",
        "from": "sender@example.com",
        "to": "me@example.com",
        "subject": "Hello",
        "date": "2026-10-11",
        "body": "Body content here",
        "contentType": "text/plain",
        "attachments": [],
    }
    render_gmail_message(msg)

    events = [
        {
            "id": "ev1",
            "summary": "Meeting",
            "start": "2026-10-12T10:00:00Z",
            "end": "2026-10-12T11:00:00Z",
            "location": "Room 1",
            "attendees": ["alice@example.com"],
        }
    ]
    render_calendar_agenda(events)

    files = [
        {
            "id": "f1",
            "name": "Report.pdf",
            "mimeType": "application/pdf",
            "modifiedTime": "2026-10-11T09:00:00Z",
        }
    ]
    render_drive_search(files)

    rows = [["Header1", "Header2"], ["Val1", "Val2"]]
    render_sheets_table(rows)
