"""Unit tests for service account validation, key management, credentials loading, and dispatch."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

import gsuite_cli.config as config
from gsuite_cli.auth.service_account import (
    copy_service_account_key,
    delete_service_account_key,
    get_dwd_setup_info,
    load_sa_credentials,
    validate_service_account_key,
)
from gsuite_cli.auth.token_store import load_account_credentials
from gsuite_cli.config import AccountConfig, DomainConfig, GSuiteConfig
from gsuite_cli.exceptions import AuthError, ConfigError, ServiceError, TokenExpiredError
from gsuite_cli.services.base import _SERVICE_CACHE, execute_api_call, get_service_client


def _write_dummy_sa_key(
    path: Path,
    key_type: str = "service_account",
    client_email: str = "sa@test-project.iam.gserviceaccount.com",
    client_id: str = "98765432101234567890",
    private_key: str = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQD...\n-----END PRIVATE KEY-----\n",
    token_uri: str = "https://oauth2.googleapis.com/token",
    project_id: str = "test-project",
) -> Path:
    """Helper to write a valid or customizable service account JSON file."""
    data = {
        "type": key_type,
        "project_id": project_id,
        "private_key_id": "dummy-key-id",
        "private_key": private_key,
        "client_email": client_email,
        "client_id": client_id,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": token_uri,
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# 1. Key validation
# ---------------------------------------------------------------------------

def test_validate_service_account_key_valid(tmp_path: Path) -> None:
    key_file = _write_dummy_sa_key(tmp_path / "valid_sa.json")
    data = validate_service_account_key(key_file)
    assert data["type"] == "service_account"
    assert data["client_email"] == "sa@test-project.iam.gserviceaccount.com"
    assert data["client_id"] == "98765432101234567890"


def test_validate_service_account_key_missing_file(tmp_path: Path) -> None:
    nonexistent = tmp_path / "missing.json"
    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(nonexistent)
    assert "not found" in str(exc_info.value)
    assert exc_info.value.details["key_path"] == str(nonexistent)


def test_validate_service_account_key_directory(tmp_path: Path) -> None:
    folder = tmp_path / "sa_dir"
    folder.mkdir()
    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(folder)
    assert "not a file" in str(exc_info.value)


def test_validate_service_account_key_bad_json(tmp_path: Path) -> None:
    bad_json = tmp_path / "corrupt.json"
    bad_json.write_text("{invalid_json:")
    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(bad_json)
    assert "Invalid JSON" in str(exc_info.value)


def test_validate_service_account_key_not_dict(tmp_path: Path) -> None:
    not_dict = tmp_path / "array.json"
    not_dict.write_text("[\"item1\", \"item2\"]")
    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(not_dict)
    assert "must be an object" in str(exc_info.value)


def test_validate_service_account_key_wrong_type(tmp_path: Path) -> None:
    wrong_type = _write_dummy_sa_key(tmp_path / "oauth_user.json", key_type="authorized_user")
    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(wrong_type)
    assert "expected 'service_account'" in str(exc_info.value)


@pytest.mark.parametrize("missing_field", ["client_email", "client_id", "private_key", "token_uri"])
def test_validate_service_account_key_missing_field(tmp_path: Path, missing_field: str) -> None:
    data = {
        "type": "service_account",
        "client_email": "sa@test.com",
        "client_id": "12345",
        "private_key": "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----\n",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    del data[missing_field]
    incomplete = tmp_path / f"missing_{missing_field}.json"
    incomplete.write_text(json.dumps(data))

    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(incomplete)
    assert f"missing or empty required fields: {missing_field}" in str(exc_info.value)


def test_validate_service_account_key_empty_field(tmp_path: Path) -> None:
    data = {
        "type": "service_account",
        "client_email": "   ",
        "client_id": "12345",
        "private_key": "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----\n",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    empty_field = tmp_path / "empty_field.json"
    empty_field.write_text(json.dumps(data))

    with pytest.raises(ConfigError) as exc_info:
        validate_service_account_key(empty_field)
    assert "missing or empty required fields: client_email" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Key copying & permissions
# ---------------------------------------------------------------------------

def test_copy_service_account_key(mock_config_dir: Path, tmp_path: Path) -> None:
    source_file = _write_dummy_sa_key(tmp_path / "downloads" / "downloaded_key.json")
    dest_path = copy_service_account_key(source_file, "corp_account")

    assert dest_path == config.KEYS_DIR / "corp_account.json"
    assert dest_path.exists()
    assert dest_path.read_text() == source_file.read_text()

    # Permissions must be 0600
    file_mode = stat.S_IMODE(os.stat(dest_path).st_mode)
    assert file_mode == 0o600

    # Re-copying when already at destination succeeds idempotently
    same_dest = copy_service_account_key(dest_path, "corp_account")
    assert same_dest == dest_path


# ---------------------------------------------------------------------------
# 3. Key deletion & reference protection
# ---------------------------------------------------------------------------

def test_delete_service_account_key_simple(mock_config_dir: Path) -> None:
    key_path = _write_dummy_sa_key(config.KEYS_DIR / "bob.json")
    assert key_path.exists()

    result = delete_service_account_key("bob")
    assert result is True
    assert not key_path.exists()

    # Deleting again returns False
    assert delete_service_account_key("bob") is False


def test_delete_service_account_key_preserves_shared_by_account(mock_config_dir: Path) -> None:
    shared_key = _write_dummy_sa_key(config.KEYS_DIR / "shared.json")
    cfg = GSuiteConfig(
        accounts={
            "alice@example.com": AccountConfig(
                auth_type="service_account",
                key_file=str(shared_key),
            ),
            "bob@example.com": AccountConfig(
                auth_type="service_account",
                key_file=str(shared_key),
            ),
        }
    )

    # Attempting to delete bob while alice still references shared_key
    result = delete_service_account_key("bob@example.com", custom_path=str(shared_key), config_obj=cfg)
    assert result is False
    assert shared_key.exists()

    # If the only reference is the identifier itself, deletion proceeds
    single_ref_cfg = GSuiteConfig(
        accounts={
            "bob@example.com": AccountConfig(
                auth_type="service_account",
                key_file=str(shared_key),
            ),
        }
    )
    result = delete_service_account_key("bob@example.com", custom_path=str(shared_key), config_obj=single_ref_cfg)
    assert result is True
    assert not shared_key.exists()


def test_delete_service_account_key_preserves_shared_by_domain(mock_config_dir: Path) -> None:
    domain_key = _write_dummy_sa_key(config.KEYS_DIR / "alpeware_domain.json")
    cfg = GSuiteConfig(
        domains={
            "alpeware.com": DomainConfig(
                domain="alpeware.com",
                key_file=str(domain_key),
            )
        }
    )

    # Attempting to delete for user 'alice' while domain still uses it returns False
    result = delete_service_account_key("alice@alpeware.com", custom_path=str(domain_key), config_obj=cfg)
    assert result is False
    assert domain_key.exists()


# ---------------------------------------------------------------------------
# 4. DWD setup info
# ---------------------------------------------------------------------------

def test_get_dwd_setup_info(tmp_path: Path) -> None:
    key_file = _write_dummy_sa_key(tmp_path / "sa.json")
    scopes = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/calendar"]
    info = get_dwd_setup_info(key_file, scopes)

    assert info["client_id"] == "98765432101234567890"
    assert info["client_email"] == "sa@test-project.iam.gserviceaccount.com"
    assert info["project_id"] == "test-project"
    assert info["scopes"] == scopes
    assert info["scopes_csv"] == ",".join(scopes)


# ---------------------------------------------------------------------------
# 5. Credentials loading (OAuth and SA)
# ---------------------------------------------------------------------------

def test_load_sa_credentials_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AuthError) as exc_info:
        load_sa_credentials(tmp_path / "nonexistent.json", scopes=["scope1"], subject="user@domain.com")
    assert "not found" in str(exc_info.value)
    assert exc_info.value.account == "user@domain.com"


@patch("google.oauth2.service_account.Credentials.from_service_account_file")
def test_load_sa_credentials_dwd_and_direct(mock_from_file: MagicMock, tmp_path: Path) -> None:
    key_file = _write_dummy_sa_key(tmp_path / "sa.json")
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

    mock_creds = MagicMock()
    mock_delegated = MagicMock()
    mock_creds.with_subject.return_value = mock_delegated
    mock_from_file.return_value = mock_creds

    # 1. DWD with subject
    creds = load_sa_credentials(key_file, scopes=scopes, subject="alice@example.com")
    mock_from_file.assert_called_with(str(key_file), scopes=scopes)
    mock_creds.with_subject.assert_called_once_with("alice@example.com")
    assert creds is mock_delegated

    # 2. Direct SA (subject=None)
    mock_from_file.reset_mock()
    mock_creds.reset_mock()
    creds_direct = load_sa_credentials(key_file, scopes=scopes, subject=None)
    mock_from_file.assert_called_with(str(key_file), scopes=scopes)
    mock_creds.with_subject.assert_not_called()
    assert creds_direct is mock_creds


@patch("google.oauth2.service_account.Credentials.from_service_account_file")
def test_load_sa_credentials_verify_refresh_unauthorized_client(
    mock_from_file: MagicMock,
    tmp_path: Path,
) -> None:
    key_file = _write_dummy_sa_key(tmp_path / "sa.json")
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

    mock_creds = MagicMock()
    mock_delegated = MagicMock()
    mock_creds.with_subject.return_value = mock_delegated
    mock_delegated.refresh.side_effect = Exception("400 unauthorized_client: Client is unauthorized.")
    mock_from_file.return_value = mock_creds

    with pytest.raises(AuthError) as exc_info:
        load_sa_credentials(key_file, scopes=scopes, subject="alice@example.com", verify_refresh=True)

    err = exc_info.value
    assert "Domain-Wide Delegation is not authorized" in str(err)
    assert err.details["client_id"] == "98765432101234567890"
    assert err.details["subject"] == "alice@example.com"
    assert err.details["scopes_csv"] == scopes[0]


@patch("google.oauth2.service_account.Credentials.from_service_account_file")
def test_load_sa_credentials_verify_refresh_generic_error(
    mock_from_file: MagicMock,
    tmp_path: Path,
) -> None:
    key_file = _write_dummy_sa_key(tmp_path / "sa.json")
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

    mock_creds = MagicMock()
    mock_creds.refresh.side_effect = Exception("Connection timed out")
    mock_from_file.return_value = mock_creds

    with pytest.raises(AuthError) as exc_info:
        load_sa_credentials(key_file, scopes=scopes, subject=None, verify_refresh=True)

    assert "Service account token refresh failed: Connection timed out" in str(exc_info.value)


@patch("gsuite_cli.auth.token_store.load_credentials")
@patch("gsuite_cli.auth.service_account.load_sa_credentials")
def test_load_account_credentials_dispatch(
    mock_load_sa: MagicMock,
    mock_load_oauth: MagicMock,
    tmp_path: Path,
) -> None:
    key_file = _write_dummy_sa_key(tmp_path / "sa.json")

    # 1. Dispatch to service_account
    sa_config = AccountConfig(
        auth_type="service_account",
        key_file=str(key_file),
        subject="alice@corp.com",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    load_account_credentials("alice@corp.com", account_config=sa_config, auto_refresh=False)
    mock_load_sa.assert_called_once_with(
        key_file,
        scopes=["https://www.googleapis.com/auth/calendar"],
        subject="alice@corp.com",
        verify_refresh=False,
    )

    # 2. Dispatch to oauth
    oauth_config = AccountConfig(
        auth_type="oauth",
        token_file="~/.config/gsuite/tokens/bob.json",
    )
    load_account_credentials("bob@corp.com", account_config=oauth_config, auto_refresh=True)
    mock_load_oauth.assert_called_once_with(
        "bob@corp.com",
        custom_path="~/.config/gsuite/tokens/bob.json",
        auto_refresh=True,
    )


# ---------------------------------------------------------------------------
# 6. Service client cache and error translation
# ---------------------------------------------------------------------------

@patch("gsuite_cli.services.base.build")
@patch("gsuite_cli.services.base.load_account_credentials")
def test_get_service_client_service_account_cache(
    mock_load_account_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    _SERVICE_CACHE.clear()
    key_file = _write_dummy_sa_key(tmp_path / "sa.json")

    mock_load_account_creds.return_value = MagicMock()
    mock_service_1 = MagicMock()
    mock_service_2 = MagicMock()
    mock_build.side_effect = [mock_service_1, mock_service_2]

    sa_config_1 = AccountConfig(
        auth_type="service_account",
        key_file=str(key_file),
        subject="alice@corp.com",
    )
    sa_config_2 = AccountConfig(
        auth_type="service_account",
        key_file=str(key_file),
        subject="bob@corp.com",
    )

    # First build for alice
    client_alice = get_service_client("alice@corp.com", "gmail", "v1", account_config=sa_config_1)
    assert client_alice is mock_service_1
    mock_load_account_creds.assert_called_with(
        "alice@corp.com",
        account_config=sa_config_1,
        auto_refresh=False,
    )

    # Second call for alice returns cached service
    client_alice_cached = get_service_client("alice@corp.com", "gmail", "v1", account_config=sa_config_1)
    assert client_alice_cached is mock_service_1

    # Call for bob with same email but different subject creates separate client
    client_bob = get_service_client("alice@corp.com", "gmail", "v1", account_config=sa_config_2)
    assert client_bob is mock_service_2


def test_execute_api_call_unauthorized_client_translation() -> None:
    mock_call = MagicMock()
    mock_call.execute.side_effect = RefreshError("unauthorized_client: Client is unauthorized")

    with pytest.raises(AuthError) as exc_info:
        execute_api_call(mock_call, "calendar", "alice@corp.com")

    assert "Domain-Wide Delegation authorization is missing" in str(exc_info.value)
    assert exc_info.value.account == "alice@corp.com"


def test_execute_api_call_generic_refresh_error() -> None:
    mock_call = MagicMock()
    mock_call.execute.side_effect = RefreshError("Token revoked by user")

    with pytest.raises(TokenExpiredError) as exc_info:
        execute_api_call(mock_call, "calendar", "alice@corp.com")

    assert "Refresh token expired or revoked" in str(exc_info.value)


def test_execute_api_call_gmail_precondition_check_failed() -> None:
    mock_resp = MagicMock()
    mock_resp.status = 400
    http_error = HttpError(mock_resp, b'{"error": {"message": "Precondition check failed."}}')

    mock_call = MagicMock()
    mock_call.execute.side_effect = http_error

    # Gmail service translates to DWD hint
    with pytest.raises(ServiceError) as exc_info:
        execute_api_call(mock_call, "gmail", "sa@proj.iam.gserviceaccount.com")

    assert "Precondition check failed" in str(exc_info.value)
    assert "Gmail API requires Domain-Wide Delegation" in str(exc_info.value)

    # Other service raises normal ServiceError without the Gmail hint
    with pytest.raises(ServiceError) as exc_info_drive:
        execute_api_call(mock_call, "drive", "sa@proj.iam.gserviceaccount.com")

    assert "Gmail API requires Domain-Wide Delegation" not in str(exc_info_drive.value)
    assert "Google drive API HTTP 400 error" in str(exc_info_drive.value)
