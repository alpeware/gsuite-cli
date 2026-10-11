"""Authentication module for gsuite-cli."""

from gsuite_cli.auth.oauth import (
    authenticate_account,
    get_client_secret_path,
    run_headless_flow,
    run_loopback_flow,
)
from gsuite_cli.auth.scopes import (
    SCOPE_PROFILES,
    resolve_scopes,
)
from gsuite_cli.auth.token_store import (
    delete_credentials,
    get_token_path,
    load_credentials,
    save_credentials,
)

__all__ = [
    "SCOPE_PROFILES",
    "authenticate_account",
    "delete_credentials",
    "get_client_secret_path",
    "get_token_path",
    "load_credentials",
    "resolve_scopes",
    "run_headless_flow",
    "run_loopback_flow",
    "save_credentials",
]
