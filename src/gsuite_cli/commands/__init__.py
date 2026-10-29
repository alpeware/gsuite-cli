"""CLI subcommands module for gsuite-cli."""

from gsuite_cli.commands.accounts_cmd import accounts_group, accounts_list
from gsuite_cli.commands.auth_cmd import auth_group
from gsuite_cli.commands.calendar_cmd import calendar_group
from gsuite_cli.commands.drive_cmd import docs_group, drive_group, sheets_group
from gsuite_cli.commands.gmail_cmd import gmail_group
from gsuite_cli.commands.skill_cmd import install_skill_cmd, skill_group
from gsuite_cli.commands.slides_cmd import slides_group
from gsuite_cli.commands.tasks_cmd import tasks_group

__all__ = [
    "accounts_group",
    "accounts_list",
    "auth_group",
    "calendar_group",
    "docs_group",
    "drive_group",
    "gmail_group",
    "install_skill_cmd",
    "sheets_group",
    "skill_group",
    "slides_group",
    "tasks_group",
]

