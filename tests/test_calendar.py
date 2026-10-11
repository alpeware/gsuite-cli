"""Tests for Google Calendar service methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gsuite_cli.services.calendar import (
    create_event,
    get_agenda,
    list_events,
    query_freebusy,
)


def test_get_agenda_parses_events() -> None:
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        "items": [
            {
                "id": "ev1",
                "summary": "Team Standup",
                "start": {"dateTime": "2026-10-12T09:00:00Z"},
                "end": {"dateTime": "2026-10-12T09:30:00Z"},
                "location": "Virtual",
                "hangoutLink": "https://meet.google.com/xyz-abc-def",
                "attendees": [{"email": "alice@example.com"}, {"email": "bob@example.com"}],
            }
        ]
    }

    with patch("gsuite_cli.services.calendar._get_calendar_service", return_value=mock_service):
        agenda = get_agenda("test@example.com", days=1, today=True)
        assert len(agenda) == 1
        item = agenda[0]
        assert item["id"] == "ev1"
        assert item["summary"] == "Team Standup"
        assert item["start"] == "2026-10-12T09:00:00Z"
        assert item["meet_link"] == "https://meet.google.com/xyz-abc-def"
        assert "alice@example.com" in item["attendees"]


def test_list_events_with_query() -> None:
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        "items": [
            {
                "id": "ev2",
                "summary": "Sprint Planning",
                "start": {"dateTime": "2026-10-13T14:00:00Z"},
                "end": {"dateTime": "2026-10-13T15:00:00Z"},
            }
        ]
    }

    with patch("gsuite_cli.services.calendar._get_calendar_service", return_value=mock_service):
        events = list_events("test@example.com", query="Sprint", limit=5)
        assert len(events) == 1
        assert events[0]["summary"] == "Sprint Planning"


def test_query_freebusy() -> None:
    mock_service = MagicMock()
    mock_service.freebusy().query().execute.return_value = {
        "calendars": {
            "colleague@example.com": {
                "busy": [{"start": "2026-10-12T13:00:00Z", "end": "2026-10-12T14:00:00Z"}]
            }
        }
    }

    with patch("gsuite_cli.services.calendar._get_calendar_service", return_value=mock_service):
        res = query_freebusy(
            "test@example.com",
            emails=["colleague@example.com"],
            start_iso="2026-10-12T09:00:00Z",
            end_iso="2026-10-12T17:00:00Z",
        )
        assert "colleague@example.com" in res["calendars"]
        busy_blocks = res["calendars"]["colleague@example.com"]
        assert len(busy_blocks) == 1
        assert busy_blocks[0]["start"] == "2026-10-12T13:00:00Z"


def test_create_event() -> None:
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        "id": "new_event_id",
        "summary": "1:1 Sync",
        "start": {"dateTime": "2026-10-12T15:00:00Z"},
        "end": {"dateTime": "2026-10-12T15:30:00Z"},
        "htmlLink": "https://calendar.google.com/event?eid=123",
    }

    with patch("gsuite_cli.services.calendar._get_calendar_service", return_value=mock_service):
        res = create_event(
            "test@example.com",
            summary="1:1 Sync",
            start_iso="2026-10-12T15:00:00Z",
            end_iso="2026-10-12T15:30:00Z",
            attendees=["partner@example.com"],
        )
        assert res["status"] == "success"
        assert res["id"] == "new_event_id"
        assert res["start"] == "2026-10-12T15:00:00Z"
