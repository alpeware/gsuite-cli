"""Root CLI entrypoint for gsuite-cli."""

from __future__ import annotations

import sys
from typing import Any

import click

from gsuite_cli import __version__
from gsuite_cli.commands import (
    accounts_group,
    auth_group,
    calendar_group,
    docs_group,
    drive_group,
    gmail_group,
    install_skill_cmd,
    sheets_group,
    skill_group,
    slides_group,
    tasks_group,
)
from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.exceptions import GSuiteError
from gsuite_cli.formatters import print_json, render_error


class GSuiteCliGroup(GSuiteGroup):
    """Custom Click group providing unified JSON and exception handling."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return super().__call__(*args, **kwargs)
        except GSuiteError as e:
            # Check if json flag was provided in args
            is_json = "--json" in sys.argv
            if is_json:
                print_json(e.to_dict())
            else:
                render_error(e.message, e.details)
            sys.exit(1)
        except Exception as e:
            is_json = "--json" in sys.argv
            if is_json:
                print_json(
                    {
                        "status": "error",
                        "error_code": "UNEXPECTED_ERROR",
                        "message": str(e),
                    }
                )
            else:
                render_error(f"Unexpected error: {e}")
            sys.exit(1)


@click.group(cls=GSuiteCliGroup)
@click.version_option(version=__version__, prog_name="gsuite")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """gsuite: Fast, multi-account CLI and Antigravity progressive skill for Google Workspace and Gmail."""
    ctx.ensure_object(dict)


# Register all subcommand groups
cli.add_command(accounts_group)
cli.add_command(auth_group)
cli.add_command(gmail_group)
cli.add_command(calendar_group)
cli.add_command(drive_group)
cli.add_command(docs_group)
cli.add_command(sheets_group)
cli.add_command(skill_group)
cli.add_command(install_skill_cmd, name="install-skill")
cli.add_command(slides_group)
cli.add_command(tasks_group)


def main() -> None:
    """Entry point for project.scripts."""
    cli(prog_name="gsuite")


if __name__ == "__main__":
    main()
