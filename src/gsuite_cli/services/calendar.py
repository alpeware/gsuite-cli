"""Google Calendar service implementation for agenda, events, freebusy, and creation."""

from __future__ import annotations

import datetime
from typing import Any

from gsuite_cli.config import AccountConfig
from gsuite_cli.services.base import execute_api_call, get_service_client


def _get_calendar_service(email_addr: str, config: AccountConfig | None = None) -> Any:
    return get_service_client(email_addr, "calendar", "v3", config)


def _format_event_time(dt_dict: dict[str, str] | None) -> str:
    """Format Google Calendar event start/end dict to readable ISO string."""
    if not dt_dict:
        return ""
    return dt_dict.get("dateTime") or dt_dict.get("date") or ""


def _parse_event_item(item: dict[str, Any]) -> dict[str, Any]:
    """Parse raw Google Calendar event item into structured dictionary."""
    attendees = [a.get("email", "") for a in item.get("attendees", []) if a.get("email")]
    meet_link = item.get("hangoutLink", "")
    if not meet_link:
        for entry in item.get("conferenceData", {}).get("entryPoints", []):
            if entry.get("entryPointType") == "video":
                meet_link = entry.get("uri", "")
                break

    return {
        "id": item.get("id"),
        "summary": item.get("summary", "(No Title)"),
        "description": item.get("description", ""),
        "start": _format_event_time(item.get("start")),
        "end": _format_event_time(item.get("end")),
        "location": item.get("location", ""),
        "meet_link": meet_link,
        "status": item.get("status", "confirmed"),
        "htmlLink": item.get("htmlLink", ""),
        "attendees": attendees,
    }


def get_agenda(
    email_addr: str,
    days: int = 1,
    today: bool = False,
    account_config: AccountConfig | None = None,
) -> list[dict[str, Any]]:
    """Retrieve upcoming events for today or next N days."""
    service = _get_calendar_service(email_addr, account_config)
    now = datetime.datetime.now(datetime.UTC)

    if today:
        # From start of today UTC to end of today UTC
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        start_dt = now
        end_dt = now + datetime.timedelta(days=days)

    time_min = start_dt.isoformat()
    time_max = end_dt.isoformat()

    events_call = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    )
    resp = execute_api_call(events_call, "Calendar", email_addr)
    items = resp.get("items", [])
    return [_parse_event_item(it) for it in items]


def list_events(
    email_addr: str,
    start_iso: str | None = None,
    end_iso: str | None = None,
    query: str | None = None,
    limit: int = 20,
    account_config: AccountConfig | None = None,
) -> list[dict[str, Any]]:
    """Search and filter calendar events."""
    service = _get_calendar_service(email_addr, account_config)
    kwargs: dict[str, Any] = {
        "calendarId": "primary",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": limit,
    }

    if start_iso:
        kwargs["timeMin"] = start_iso
    else:
        # Default start from current time
        kwargs["timeMin"] = datetime.datetime.now(datetime.UTC).isoformat()

    if end_iso:
        kwargs["timeMax"] = end_iso
    if query:
        kwargs["q"] = query

    events_call = service.events().list(**kwargs)
    resp = execute_api_call(events_call, "Calendar", email_addr)
    items = resp.get("items", [])
    return [_parse_event_item(it) for it in items]


def query_freebusy(
    email_addr: str,
    emails: list[str],
    start_iso: str,
    end_iso: str,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Query free/busy schedule across one or more email addresses."""
    service = _get_calendar_service(email_addr, account_config)
    body = {
        "timeMin": start_iso,
        "timeMax": end_iso,
        "items": [{"id": e} for e in emails],
    }

    fb_call = service.freebusy().query(body=body)
    resp = execute_api_call(fb_call, "Calendar", email_addr)

    calendars_resp = resp.get("calendars", {})
    parsed_schedules: dict[str, list[dict[str, str]]] = {}

    for cal_id, data in calendars_resp.items():
        busy_blocks = data.get("busy", [])
        parsed_schedules[cal_id] = [
            {"start": block.get("start", ""), "end": block.get("end", "")} for block in busy_blocks
        ]

    return {
        "timeMin": start_iso,
        "timeMax": end_iso,
        "calendars": parsed_schedules,
    }


def create_event(
    email_addr: str,
    summary: str,
    start_iso: str,
    end_iso: str,
    attendees: list[str] | None = None,
    description: str | None = None,
    location: str | None = None,
    meet: bool = False,
    send_updates: str | None = None,
    account_config: AccountConfig | None = None,
) -> dict[str, Any]:
    """Create a new event on the primary calendar."""
    service = _get_calendar_service(email_addr, account_config)
    body: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }

    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    insert_kwargs: dict[str, Any] = {"calendarId": "primary", "body": body}
    if meet:
        import uuid

        body["conferenceData"] = {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        insert_kwargs["conferenceDataVersion"] = 1
    if send_updates:
        insert_kwargs["sendUpdates"] = send_updates

    insert_call = service.events().insert(**insert_kwargs)
    resp = execute_api_call(insert_call, "Calendar", email_addr)

    meet_link = resp.get("hangoutLink", "")
    return {
        "status": "success",
        "action": "event_created",
        "id": resp.get("id"),
        "summary": resp.get("summary"),
        "start": _format_event_time(resp.get("start")),
        "end": _format_event_time(resp.get("end")),
        "htmlLink": resp.get("htmlLink", ""),
        "meet_link": meet_link,
    }
