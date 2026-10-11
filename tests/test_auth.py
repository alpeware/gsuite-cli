"""Tests for token storage, permissions, scopes, and OAuth helper functions."""

from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gsuite_cli.auth.oauth import extract_auth_code
from gsuite_cli.auth.scopes import (
    SCOPE_GMAIL_READONLY,
    SCOPE_PROFILES,
    resolve_scopes,
)
from gsuite_cli.auth.token_store import (
    delete_credentials,
    load_credentials,
    save_credentials,
)
from gsuite_cli.exceptions import AuthError


def test_scopes_resolution() -> None:
    standard = resolve_scopes("standard")
    assert standard == SCOPE_PROFILES["standard"]

    read_only = resolve_scopes("read-only")
    assert read_only == SCOPE_PROFILES["read-only"]
    assert SCOPE_GMAIL_READONLY in read_only

    custom = resolve_scopes(
        "https://www.googleapis.com/auth/custom, https://www.googleapis.com/auth/other"
    )
    assert len(custom) == 2
    assert custom[0] == "https://www.googleapis.com/auth/custom"


def test_extract_auth_code_from_raw() -> None:
    code = "4/0Abc123-xyz_test"
    assert extract_auth_code(code) == code


def test_extract_auth_code_from_loopback_url() -> None:
    url = "http://localhost:8085/?state=xyz&code=4/0AeanS0ABCDEF12345&scope=email"
    assert extract_auth_code(url) == "4/0AeanS0ABCDEF12345"


def test_extract_auth_code_invalid_url_raises_error() -> None:
    url = "http://localhost:8085/?state=xyz"
    with pytest.raises(AuthError):
        extract_auth_code(url)


def test_token_save_and_load(mock_config_dir: Path, mock_credentials: MagicMock) -> None:
    email = "test@example.com"
    token_path = save_credentials(email, mock_credentials)

    assert token_path.exists()

    # Verify 0600 file permission
    mode = stat.S_IMODE(token_path.stat().st_mode)
    assert mode == 0o600

    loaded = load_credentials(email, auto_refresh=False)
    assert loaded.refresh_token == "mock-refresh-token"


def test_delete_credentials(mock_config_dir: Path, mock_credentials: MagicMock) -> None:
    email = "delete_me@example.com"
    token_path = save_credentials(email, mock_credentials)
    assert token_path.exists()

    deleted = delete_credentials(email)
    assert deleted is True
    assert not token_path.exists()

    # Second delete returns False
    assert delete_credentials(email) is False


def test_missing_token_raises_auth_error(mock_config_dir: Path) -> None:
    with pytest.raises(AuthError) as exc_info:
        load_credentials("nonexistent@example.com")
    assert "Token file not found" in str(exc_info.value)
