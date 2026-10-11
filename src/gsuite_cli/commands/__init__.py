"""CLI subcommands module for gsuite-cli."""

from gsuite_cli.commands.auth_cmd import auth_group
from gsuite_cli.commands.calendar_cmd import calendar_group
from gsuite_cli.commands.drive_cmd import docs_group, drive_group, sheets_group
from gsuite_cli.commands.gmail_cmd import gmail_group
from gsuite_cli.commands.slides_cmd import slides_group
from gsuite_cli.commands.tasks_cmd import tasks_group

__all__ = [
    "auth_group",
    "calendar_group",
    "docs_group",
    "drive_group",
    "gmail_group",
    "sheets_group",
    "slides_group",
    "tasks_group",
]

