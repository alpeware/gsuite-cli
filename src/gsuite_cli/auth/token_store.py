"""Token storage, security permission enforcement, and automated token refresh."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from gsuite_cli.auth.scopes import resolve_scopes
from gsuite_cli.config import TOKENS_DIR, ensure_config_dir
from gsuite_cli.exceptions import AuthError, TokenExpiredError

if TYPE_CHECKING:
    from gsuite_cli.config import AccountConfig


def enforce_secure_permissions(path: Path) -> None:
    """Ensure token directory is 0700 and token files are 0600."""
    try:
        if path.is_dir():
            current_mode = stat.S_IMODE(os.stat(path).st_mode)
            if current_mode != 0o700:
                os.chmod(path, 0o700)
        elif path.is_file():
            current_mode = stat.S_IMODE(os.stat(path).st_mode)
            if current_mode != 0o600:
                os.chmod(path, 0o600)
    except OSError:
        pass


def get_token_path(email: str, custom_path: str | None = None) -> Path:
    """Resolve token file path for an account."""
    if custom_path:
        return Path(os.path.expanduser(custom_path))
    ensure_config_dir()
    return TOKENS_DIR / f"{email}.json"


def save_credentials(email: str, credentials: Credentials, custom_path: str | None = None) -> Path:
    """Persist credentials to token file with 0600 permissions."""
    ensure_config_dir()
    token_path = get_token_path(email, custom_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    enforce_secure_permissions(token_path.parent)

    token_json = credentials.to_json()

    with tempfile.NamedTemporaryFile("w", dir=token_path.parent, delete=False) as tf:
        tf.write(token_json)
        temp_name = tf.name

    try:
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, token_path)
    except Exception as e:
        if os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        raise AuthError(f"Failed to persist token file {token_path}: {e}", account=email)

    return token_path


def load_credentials(
    email: str,
    custom_path: str | None = None,
    auto_refresh: bool = True,
) -> Credentials:
    """Load credentials from disk and optionally auto-refresh if expired.

    Raises TokenExpiredError or AuthError on failure.
    """
    token_path = get_token_path(email, custom_path)
    if not token_path.exists():
        raise AuthError(
            f"Token file not found for {email} at {token_path}. Run 'gsuite auth add {email}'.",
            account=email,
        )

    enforce_secure_permissions(token_path)

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            token_data = json.load(f)
        creds = Credentials.from_authorized_user_info(token_data)
    except Exception as e:
        raise AuthError(f"Failed to parse credentials from {token_path}: {e}", account=email)

    if auto_refresh and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed credentials back to disk
            save_credentials(email, creds, custom_path)
        except Exception as e:
            raise TokenExpiredError(
                f"Failed to refresh expired token for {email}: {e}. Run 'gsuite auth add {email}'.",
                account=email,
            )

    if creds.expired and not creds.refresh_token:
        raise TokenExpiredError(
            f"Token for {email} is expired and has no refresh token. Re-run 'gsuite auth add {email}'.",
            account=email,
        )

    return creds


def delete_credentials(email: str, custom_path: str | None = None) -> bool:
    """Delete credentials file for an account. Returns True if deleted, False if did not exist."""
    token_path = get_token_path(email, custom_path)
    if token_path.exists():
        try:
            token_path.unlink()
            return True
        except OSError as e:
            raise AuthError(f"Failed to remove token file {token_path}: {e}", account=email)
    return False


def load_account_credentials(
    email: str,
    account_config: AccountConfig | None = None,
    auto_refresh: bool = True,
) -> Any:
    """Load credentials for an account, dispatching to either OAuth or Service Account."""
    if account_config and account_config.auth_type == "service_account":
        from gsuite_cli.auth.service_account import load_sa_credentials

        key_path = account_config.resolved_key_path(email)
        subject = account_config.resolved_subject(email)
        scopes = account_config.scopes or resolve_scopes("standard")
        return load_sa_credentials(
            key_path,
            scopes=scopes,
            subject=subject,
            verify_refresh=auto_refresh,
        )

    token_path = account_config.token_file if account_config else None
    return load_credentials(email, custom_path=token_path, auto_refresh=auto_refresh)
