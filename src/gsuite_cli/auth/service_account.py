"""Service account authentication and Domain-Wide Delegation (DWD) primitives."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account

import gsuite_cli.config as config
from gsuite_cli.auth.token_store import enforce_secure_permissions
from gsuite_cli.exceptions import AuthError, ConfigError

REQUIRED_SA_FIELDS = ("client_email", "client_id", "private_key", "token_uri")


def validate_service_account_key(key_path: str | Path) -> dict[str, Any]:
    """Validate a Google Cloud service account JSON key file.

    Raises ConfigError if the file does not exist, contains invalid JSON,
    is not of type 'service_account', or is missing mandatory fields.
    """
    path = Path(os.path.expanduser(str(key_path)))
    if not path.exists():
        raise ConfigError(
            f"Service account key file not found: {path}",
            details={"key_path": str(path)},
        )
    if not path.is_file():
        raise ConfigError(
            f"Service account key path is not a file: {path}",
            details={"key_path": str(path)},
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"Invalid JSON in service account key file {path}: {e}",
            details={"key_path": str(path)},
        )
    except Exception as e:
        raise ConfigError(
            f"Failed to read service account key file {path}: {e}",
            details={"key_path": str(path)},
        )

    if not isinstance(data, dict):
        raise ConfigError(
            f"Service account key JSON root must be an object in {path}.",
            details={"key_path": str(path)},
        )

    key_type = data.get("type")
    if key_type != "service_account":
        raise ConfigError(
            f"Invalid key type in {path}: expected 'service_account', got '{key_type}'.",
            details={"key_path": str(path), "type": key_type},
        )

    missing = [
        field
        for field in REQUIRED_SA_FIELDS
        if not data.get(field) or not str(data.get(field)).strip()
    ]
    if missing:
        raise ConfigError(
            f"Service account key {path} missing or empty required fields: {', '.join(missing)}.",
            details={"key_path": str(path), "missing_fields": missing},
        )

    return data


def copy_service_account_key(source_path: str | Path, identifier: str) -> Path:
    """Validate and copy a service account key into ~/.config/gsuite/keys/<identifier>.json.

    Ensures the target file is written atomically with 0600 permissions.
    """
    validate_service_account_key(source_path)
    config.ensure_config_dir()

    dest_path = config.KEYS_DIR / f"{identifier}.json"
    source_expanded = Path(os.path.expanduser(str(source_path)))

    if source_expanded.resolve() != dest_path.resolve():
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        content = source_expanded.read_bytes()

        with tempfile.NamedTemporaryFile("wb", dir=dest_path.parent, delete=False) as tf:
            tf.write(content)
            temp_name = tf.name

        try:
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, dest_path)
        except Exception as e:
            if os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except OSError:
                    pass
            raise ConfigError(f"Failed to copy service account key to {dest_path}: {e}")

    enforce_secure_permissions(dest_path)
    return dest_path


def delete_service_account_key(
    identifier: str,
    custom_path: str | None = None,
    config_obj: config.GSuiteConfig | None = None,
) -> bool:
    """Delete a service account key file.

    If config_obj is provided, checks if any other account or domain references
    the resolved key path. If still referenced, does not delete and returns False.
    Returns True if unlinked, False otherwise.
    """
    target_path = (
        Path(os.path.expanduser(custom_path))
        if custom_path
        else config.KEYS_DIR / f"{identifier}.json"
    )

    if config_obj:
        target_resolved = target_path.expanduser().resolve()
        # Check if other accounts reference this key file
        for email, acc in config_obj.accounts.items():
            if email.lower() != identifier.lower() and acc.auth_type == "service_account":
                if acc.resolved_key_path(email).expanduser().resolve() == target_resolved:
                    return False

        # Check if domains reference this key file
        for dom_name, dom_cfg in config_obj.domains.items():
            if dom_name.lower() != identifier.lower():
                if dom_cfg.resolved_key_path().expanduser().resolve() == target_resolved:
                    return False

    if target_path.exists():
        try:
            target_path.unlink()
            return True
        except OSError as e:
            raise ConfigError(f"Failed to remove service account key file {target_path}: {e}")

    return False


def get_dwd_setup_info(key_path: str | Path, scopes: list[str]) -> dict[str, Any]:
    """Extract information required to configure Domain-Wide Delegation in Google Workspace."""
    data = validate_service_account_key(key_path)
    return {
        "client_id": data["client_id"],
        "client_email": data["client_email"],
        "project_id": data.get("project_id", ""),
        "scopes": scopes,
        "scopes_csv": ",".join(scopes),
    }


def load_sa_credentials(
    key_path: str | Path,
    scopes: list[str],
    subject: str | None = None,
    verify_refresh: bool = False,
) -> service_account.Credentials:
    """Load Google service account credentials from a key file.

    Optionally impersonates a Google Workspace user (subject) via Domain-Wide Delegation
    and verifies token generation if verify_refresh is True.
    """
    path = Path(os.path.expanduser(str(key_path)))
    if not path.exists():
        raise AuthError(
            f"Service account key file not found at {path}.",
            account=subject,
        )

    enforce_secure_permissions(path)
    validate_service_account_key(path)

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(path),
            scopes=scopes,
        )
    except Exception as e:
        raise AuthError(
            f"Failed to load service account credentials from {path}: {e}",
            account=subject,
        )

    if subject:
        creds = creds.with_subject(subject)

    if verify_refresh:
        try:
            creds.refresh(Request())
        except Exception as e:
            if "unauthorized_client" in str(e).lower():
                info = get_dwd_setup_info(path, scopes)
                raise AuthError(
                    f"Domain-Wide Delegation is not authorized in Google Workspace Admin Console "
                    f"for client ID {info['client_id']} and subject '{subject}'. "
                    f"Authorize this client ID in Google Admin Console -> Security -> API controls -> "
                    f"Domain-wide delegation with scopes: {info['scopes_csv']}",
                    account=subject,
                    details={
                        "client_id": info["client_id"],
                        "client_email": info["client_email"],
                        "subject": subject,
                        "scopes_csv": info["scopes_csv"],
                    },
                )
            raise AuthError(
                f"Service account token refresh failed: {e}",
                account=subject,
            )

    return creds
