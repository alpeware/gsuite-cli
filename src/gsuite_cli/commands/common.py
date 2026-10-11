"""Common Click command and group classes for global flags (--json, -v, -q)."""

from __future__ import annotations

from typing import Any

import click


class GSuiteCommand(click.Command):
    """Click command that automatically supports global flags placed at command level."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        existing = {param.name for param in self.params}
        if "json" not in existing:
            self.params.append(
                click.Option(
                    ["--json"],
                    "json",
                    is_flag=True,
                    help="Output responses as deterministic JSON to stdout",
                )
            )
        if "verbose" not in existing:
            self.params.append(
                click.Option(
                    ["-v", "--verbose"],
                    "verbose",
                    is_flag=True,
                    help="Enable verbose debug logs to stderr",
                )
            )
        if "quiet" not in existing:
            self.params.append(
                click.Option(
                    ["-q", "--quiet"], "quiet", is_flag=True, help="Suppress informational banners"
                )
            )

    def invoke(self, ctx: click.Context) -> Any:
        ctx.ensure_object(dict)
        if ctx.params.pop("json", None):
            ctx.obj["json"] = True
        if ctx.params.pop("verbose", None):
            ctx.obj["verbose"] = True
        if ctx.params.pop("quiet", None):
            ctx.obj["quiet"] = True
        return super().invoke(ctx)


class GSuiteGroup(click.Group):
    """Click group that sets GSuiteCommand as default command class."""

    command_class = GSuiteCommand

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        existing = {param.name for param in self.params}
        if "json" not in existing:
            self.params.append(
                click.Option(
                    ["--json"],
                    "json",
                    is_flag=True,
                    help="Output responses as deterministic JSON to stdout",
                )
            )
        if "verbose" not in existing:
            self.params.append(
                click.Option(
                    ["-v", "--verbose"],
                    "verbose",
                    is_flag=True,
                    help="Enable verbose debug logs to stderr",
                )
            )
        if "quiet" not in existing:
            self.params.append(
                click.Option(
                    ["-q", "--quiet"], "quiet", is_flag=True, help="Suppress informational banners"
                )
            )

    def group(self, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("cls", GSuiteGroup)
        return super().group(*args, **kwargs)

    def command(self, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("cls", GSuiteCommand)
        return super().command(*args, **kwargs)

    def invoke(self, ctx: click.Context) -> Any:
        ctx.ensure_object(dict)
        if ctx.params.pop("json", None):
            ctx.obj["json"] = True
        if ctx.params.pop("verbose", None):
            ctx.obj["verbose"] = True
        if ctx.params.pop("quiet", None):
            ctx.obj["quiet"] = True
        return super().invoke(ctx)
