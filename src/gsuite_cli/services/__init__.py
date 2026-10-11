"""Google API services module for gsuite-cli."""

from gsuite_cli.services.base import execute_api_call, get_service_client
from gsuite_cli.services.calendar import (
    create_event,
    get_agenda,
    list_events,
    query_freebusy,
)
from gsuite_cli.services.docs_sheets import (
    append_sheet,
    read_doc_as_markdown,
    read_sheet,
)
from gsuite_cli.services.drive import export_file, search_files
from gsuite_cli.services.gmail import (
    create_draft,
    get_thread,
    modify_message,
    read_message,
    search_messages,
    send_message,
)

__all__ = [
    "append_sheet",
    "create_draft",
    "create_event",
    "execute_api_call",
    "export_file",
    "get_agenda",
    "get_service_client",
    "get_thread",
    "list_events",
    "modify_message",
    "query_freebusy",
    "read_doc_as_markdown",
    "read_message",
    "read_sheet",
    "search_files",
    "search_messages",
    "send_message",
]
