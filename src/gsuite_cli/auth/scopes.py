"""OAuth 2.0 Scopes and scope profiles for gsuite-cli."""

from __future__ import annotations

# Gmail API scopes
SCOPE_GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
SCOPE_GMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"
SCOPE_GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
SCOPE_GMAIL_COMPOSE = "https://www.googleapis.com/auth/gmail.compose"

# Calendar API scopes
SCOPE_CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
SCOPE_CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"
SCOPE_CALENDAR_FULL = "https://www.googleapis.com/auth/calendar"

# Drive / Docs / Sheets API scopes
SCOPE_DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
SCOPE_DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
SCOPE_DRIVE_FULL = "https://www.googleapis.com/auth/drive"
SCOPE_DOCUMENTS = "https://www.googleapis.com/auth/documents"
SCOPE_SPREADSHEETS = "https://www.googleapis.com/auth/spreadsheets"

# Tasks & Slides API scopes
SCOPE_TASKS_READONLY = "https://www.googleapis.com/auth/tasks.readonly"
SCOPE_TASKS = "https://www.googleapis.com/auth/tasks"
SCOPE_PRESENTATIONS_READONLY = "https://www.googleapis.com/auth/presentations.readonly"
SCOPE_PRESENTATIONS = "https://www.googleapis.com/auth/presentations"

# Pre-defined scope profiles
SCOPE_PROFILES: dict[str, list[str]] = {
    "read-only": [
        SCOPE_GMAIL_READONLY,
        SCOPE_CALENDAR_READONLY,
        SCOPE_DRIVE_READONLY,
        SCOPE_TASKS_READONLY,
        SCOPE_PRESENTATIONS_READONLY,
    ],
    "standard": [
        SCOPE_GMAIL_MODIFY,
        SCOPE_CALENDAR_EVENTS,
        SCOPE_DRIVE_FILE,
        SCOPE_DOCUMENTS,
        SCOPE_SPREADSHEETS,
        SCOPE_TASKS,
        SCOPE_PRESENTATIONS,
    ],
    "full": [
        SCOPE_GMAIL_SEND,
        SCOPE_GMAIL_MODIFY,
        SCOPE_CALENDAR_FULL,
        SCOPE_DRIVE_FULL,
        SCOPE_DOCUMENTS,
        SCOPE_SPREADSHEETS,
        SCOPE_TASKS,
        SCOPE_PRESENTATIONS,
    ],
}


def resolve_scopes(profile_or_scopes: str | list[str] | None = None) -> list[str]:
    """Resolve scope list from profile name ('standard', 'read-only', 'full') or explicit list."""
    if not profile_or_scopes:
        return list(SCOPE_PROFILES["standard"])

    if isinstance(profile_or_scopes, str):
        key = profile_or_scopes.lower()
        if key in SCOPE_PROFILES:
            return list(SCOPE_PROFILES[key])
        # Comma-separated scopes or single scope URL
        return [s.strip() for s in profile_or_scopes.split(",") if s.strip()]

    return list(profile_or_scopes)
