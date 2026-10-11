"""Tests for Gmail service methods."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

from gsuite_cli.services.gmail import (
    create_draft,
    modify_message,
    read_message,
    search_messages,
    send_message,
)


def test_search_messages_returns_parsed_list() -> None:
    mock_service = MagicMock()
    # Mock list call
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}]
    }

    # Mock get call for metadata
    def mock_get(userId: str, id: str, **kwargs: dict) -> MagicMock:
        call = MagicMock()
        call.execute.return_value = {
            "id": id,
            "threadId": f"th_{id}",
            "snippet": f"Snippet for {id}",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "Subject", "value": f"Subject {id}"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Date", "value": "2026-10-11T12:00:00Z"},
                ]
            },
        }
        return call

    mock_service.users().messages().get = mock_get

    with patch("gsuite_cli.services.gmail._get_gmail_service", return_value=mock_service):
        results = search_messages("test@example.com", "is:unread", limit=2)
        assert len(results) == 2
        assert results[0]["id"] == "msg1"
        assert results[0]["subject"] == "Subject msg1"
        assert results[0]["from"] == "sender@example.com"


def test_read_message_decodes_body() -> None:
    mock_service = MagicMock()
    encoded_body = base64.urlsafe_b64encode(b"Hello world from Gmail!").decode("ASCII")

    mock_service.users().messages().get().execute.return_value = {
        "id": "msg123",
        "threadId": "th123",
        "snippet": "Hello world...",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "bob@example.com"},
                {"name": "Date", "value": "2026-10-11T12:00:00Z"},
            ],
            "mimeType": "text/plain",
            "body": {"data": encoded_body},
            "parts": [],
        },
    }

    with patch("gsuite_cli.services.gmail._get_gmail_service", return_value=mock_service):
        msg = read_message("test@example.com", "msg123")
        assert msg["id"] == "msg123"
        assert msg["subject"] == "Test Subject"
        assert msg["body"] == "Hello world from Gmail!"
        assert msg["from"] == "alice@example.com"


def test_create_draft() -> None:
    mock_service = MagicMock()
    mock_service.users().drafts().create().execute.return_value = {
        "id": "draft_abc",
        "message": {"id": "msg_abc"},
    }

    with patch("gsuite_cli.services.gmail._get_gmail_service", return_value=mock_service):
        res = create_draft(
            "sender@example.com",
            to="recipient@example.com",
            subject="Draft Subject",
            body="Draft Body",
        )
        assert res["status"] == "success"
        assert res["draftId"] == "draft_abc"


def test_send_message() -> None:
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.return_value = {
        "id": "msg_sent",
        "threadId": "thread_sent",
    }

    with patch("gsuite_cli.services.gmail._get_gmail_service", return_value=mock_service):
        res = send_message(
            "sender@example.com",
            to="recipient@example.com",
            subject="Finalized Notice",
            body="Content...",
        )
        assert res["status"] == "success"
        assert res["id"] == "msg_sent"


def test_modify_message() -> None:
    mock_service = MagicMock()
    mock_service.users().messages().modify().execute.return_value = {
        "id": "msg1",
        "labelIds": ["IMPORTANT"],
    }

    with patch("gsuite_cli.services.gmail._get_gmail_service", return_value=mock_service):
        res = modify_message("sender@example.com", "msg1", mark_read=True, archive=True)
        assert res["status"] == "success"
        assert res["labels"] == ["IMPORTANT"]
