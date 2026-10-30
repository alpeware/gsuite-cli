"""Pytest configuration and shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.oauth2.credentials import Credentials

from gsuite_cli.config import AccountConfig, GSuiteConfig, GSuiteSettings


@pytest.fixture
def mock_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create and monkeypatch isolated config, token, and key directories."""
    cfg_dir = tmp_path / "gsuite"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    tokens_dir = cfg_dir / "tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    keys_dir = cfg_dir / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.json"
    client_secret_file = cfg_dir / "client_secret.json"

    # Write dummy client secret
    client_secret_file.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "mock-client-id.apps.googleusercontent.com",
                    "client_secret": "mock-client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
        )
    )

    monkeypatch.setattr("gsuite_cli.config.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("gsuite_cli.config.CONFIG_FILE", cfg_file)
    monkeypatch.setattr("gsuite_cli.config.TOKENS_DIR", tokens_dir)
    monkeypatch.setattr("gsuite_cli.config.KEYS_DIR", keys_dir)
    monkeypatch.setattr("gsuite_cli.config.CLIENT_SECRET_FILE", client_secret_file)

    monkeypatch.setattr("gsuite_cli.auth.token_store.TOKENS_DIR", tokens_dir)
    monkeypatch.setattr("gsuite_cli.auth.oauth.CLIENT_SECRET_FILE", client_secret_file)

    return cfg_dir


@pytest.fixture
def sample_config() -> GSuiteConfig:
    """Return a pre-populated GSuiteConfig with multiple accounts and labels."""
    return GSuiteConfig(
        default_account="alpeware@gmail.com",
        accounts={
            "alpeware@gmail.com": AccountConfig(
                alias="personal",
                labels=["personal", "alpeware", "primary"],
                token_file="~/.config/gsuite/tokens/alpeware@gmail.com.json",
                scopes=["https://www.googleapis.com/auth/gmail.modify"],
            ),
            "root@alpeware.com": AccountConfig(
                alias="work",
                labels=["work", "alpeware", "enterprise"],
                token_file="~/.config/gsuite/tokens/root@alpeware.com.json",
                scopes=["https://www.googleapis.com/auth/gmail.modify"],
            ),
            "foundation@nonprofit.org": AccountConfig(
                alias="foundation",
                labels=["foundation", "work", "nonprofit"],
                token_file="~/.config/gsuite/tokens/foundation@nonprofit.org.json",
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            ),
        },
        settings=GSuiteSettings(max_results_default=10),
    )


@pytest.fixture
def mock_credentials() -> MagicMock:
    """Return a mock Google OAuth2 Credentials object."""
    creds = MagicMock(spec=Credentials)
    creds.valid = True
    creds.expired = False
    creds.refresh_token = "mock-refresh-token"
    creds.token = "mock-access-token"
    creds.to_json.return_value = json.dumps(
        {
            "token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "mock-client-id",
            "client_secret": "mock-client-secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
        }
    )
    return creds
