"""Router package for account and label targeting and concurrent execution."""

from gsuite_cli.router.executor import (
    AccountResult,
    AggregatedResult,
    execute_across_targets,
)
from gsuite_cli.router.resolver import resolve_command_targets

__all__ = [
    "AccountResult",
    "AggregatedResult",
    "execute_across_targets",
    "resolve_command_targets",
]
