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
from gsuite_cli.auth.service_account import (
    copy_service_account_key,
    delete_service_account_key,
    get_dwd_setup_info,
    load_sa_credentials,
    validate_service_account_key,
)
from gsuite_cli.auth.token_store import (
    delete_credentials,
    enforce_secure_permissions,
    get_token_path,
    load_account_credentials,
    load_credentials,
    save_credentials,
)

__all__ = [
    "SCOPE_PROFILES",
    "authenticate_account",
    "copy_service_account_key",
    "delete_credentials",
    "delete_service_account_key",
    "enforce_secure_permissions",
    "get_client_secret_path",
    "get_dwd_setup_info",
    "get_token_path",
    "load_account_credentials",
    "load_credentials",
    "load_sa_credentials",
    "resolve_scopes",
    "run_headless_flow",
    "run_loopback_flow",
    "save_credentials",
    "validate_service_account_key",
]
