"""Tests for configuration parsing, persistence, and target resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gsuite_cli import config as gsuite_config
from gsuite_cli.config import (
    AccountConfig,
    DomainConfig,
    GSuiteConfig,
    load_config,
    save_config,
)
from gsuite_cli.exceptions import ConfigError, TargetingError


def test_empty_config_loads_defaults(mock_config_dir: Path) -> None:
    config = load_config()
    assert config.version == "1.0"
    assert config.default_account is None
    assert len(config.accounts) == 0


def test_save_and_load_config(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    loaded = load_config()

    assert loaded.default_account == "alpeware@gmail.com"
    assert len(loaded.accounts) == 3
    assert loaded.accounts["alpeware@gmail.com"].alias == "personal"
    assert "work" in loaded.accounts["root@alpeware.com"].labels


def test_get_account_by_email_and_alias(sample_config: GSuiteConfig) -> None:
    # Direct email lookup
    email, acc = sample_config.get_account("alpeware@gmail.com")
    assert email == "alpeware@gmail.com"
    assert acc.alias == "personal"

    # Alias lookup
    email, acc = sample_config.get_account("work")
    assert email == "root@alpeware.com"

    # Nonexistent account raises TargetingError
    with pytest.raises(TargetingError) as exc_info:
        sample_config.get_account("unknown@example.com")
    assert "not found" in str(exc_info.value)


def test_resolve_targets_explicit_account(sample_config: GSuiteConfig) -> None:
    targets = sample_config.resolve_targets(account="personal")
    assert len(targets) == 1
    assert targets[0][0] == "alpeware@gmail.com"


def test_resolve_targets_label_grouping(sample_config: GSuiteConfig) -> None:
    targets = sample_config.resolve_targets(label="work")
    assert len(targets) == 2
    emails = {t[0] for t in targets}
    assert emails == {"root@alpeware.com", "foundation@nonprofit.org"}


def test_resolve_targets_unknown_label_raises_error(sample_config: GSuiteConfig) -> None:
    with pytest.raises(TargetingError) as exc_info:
        sample_config.resolve_targets(label="nonexistent_tag")
    assert "No accounts found with label" in str(exc_info.value)


def test_resolve_targets_all_flag(sample_config: GSuiteConfig) -> None:
    targets = sample_config.resolve_targets(all_accounts=True)
    assert len(targets) == 3


def test_resolve_targets_default_fallback(sample_config: GSuiteConfig) -> None:
    targets = sample_config.resolve_targets()
    assert len(targets) == 1
    assert targets[0][0] == "alpeware@gmail.com"


def test_corrupt_config_raises_config_error(mock_config_dir: Path) -> None:
    cfg_file = mock_config_dir / "config.json"
    cfg_file.write_text("{invalid_json:")

    with pytest.raises(ConfigError):
        load_config()


def test_account_config_defaults_and_helpers(mock_config_dir: Path) -> None:
    # 1. Defaults and backward compatibility
    acc = AccountConfig()
    assert acc.auth_type == "oauth"
    assert acc.token_file is None
    assert acc.key_file is None
    assert acc.subject is None
    assert acc.impersonate is True
    assert acc.scopes == []
    assert acc.created_at is None

    # Backward compatibility with existing oauth config
    acc_oauth = AccountConfig(
        alias="work",
        labels=["team"],
        token_file="~/.config/gsuite/tokens/work.json",
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
    )
    assert acc_oauth.auth_type == "oauth"
    assert acc_oauth.resolved_token_path("work@example.com") == Path(
        os.path.expanduser("~/.config/gsuite/tokens/work.json")
    )
    assert acc_oauth.resolved_subject("work@example.com") is None

    # 2. resolved_key_path
    assert (
        acc.resolved_key_path("user@example.com")
        == gsuite_config.KEYS_DIR / "user@example.com.json"
    )
    assert (
        acc.resolved_key_path("user@example.com")
        == mock_config_dir / "keys" / "user@example.com.json"
    )

    acc_custom_key = AccountConfig(
        auth_type="service_account",
        key_file="~/custom_keys/sa.json",
    )
    assert acc_custom_key.resolved_key_path("user@example.com") == Path(
        os.path.expanduser("~/custom_keys/sa.json")
    )

    # 3. resolved_subject
    # OAuth always returns None
    acc_oauth_with_subject = AccountConfig(
        auth_type="oauth",
        subject="admin@example.com",
        impersonate=True,
    )
    assert acc_oauth_with_subject.resolved_subject("user@example.com") is None

    # SA with impersonate=False returns None
    acc_sa_no_impersonate = AccountConfig(
        auth_type="service_account",
        impersonate=False,
        subject="admin@example.com",
    )
    assert acc_sa_no_impersonate.resolved_subject("user@example.com") is None

    # SA with impersonate=True and no subject returns email (DWD default)
    acc_dwd_default = AccountConfig(
        auth_type="service_account",
        impersonate=True,
        subject=None,
    )
    assert acc_dwd_default.resolved_subject("alice@example.com") == "alice@example.com"

    # SA with impersonate=True and explicit subject
    acc_dwd_explicit = AccountConfig(
        auth_type="service_account",
        impersonate=True,
        subject="admin@example.com",
    )
    assert acc_dwd_explicit.resolved_subject("alice@example.com") == "admin@example.com"


def test_domain_config_persistence_and_loading(mock_config_dir: Path) -> None:
    dom = DomainConfig(
        domain="alpeware.com",
        key_file="~/.config/gsuite/keys/alpeware.json",
        scopes=["https://www.googleapis.com/auth/calendar"],
        labels=["enterprise", "sa"],
        created_at="2026-10-30T20:00:00Z",
    )
    assert dom.resolved_key_path() == Path(os.path.expanduser("~/.config/gsuite/keys/alpeware.json"))

    config = GSuiteConfig(
        default_account=None,
        accounts={},
        domains={"alpeware.com": dom},
    )
    save_config(config)

    loaded = load_config()
    assert "alpeware.com" in loaded.domains
    loaded_dom = loaded.domains["alpeware.com"]
    assert loaded_dom.domain == "alpeware.com"
    assert loaded_dom.key_file == "~/.config/gsuite/keys/alpeware.json"
    assert loaded_dom.scopes == ["https://www.googleapis.com/auth/calendar"]
    assert loaded_dom.labels == ["enterprise", "sa"]
    assert loaded_dom.created_at == "2026-10-30T20:00:00Z"
    assert loaded_dom.resolved_key_path() == Path(
        os.path.expanduser("~/.config/gsuite/keys/alpeware.json")
    )


def test_wildcard_domain_resolution_and_precedence(mock_config_dir: Path) -> None:
    dom_cfg = DomainConfig(
        domain="alpeware.com",
        key_file="/etc/gsuite/alpeware-sa.json",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        labels=["work", "dwd"],
        created_at="2026-10-30T10:00:00Z",
    )
    config = GSuiteConfig(domains={"alpeware.com": dom_cfg})

    # 1. Wildcard resolution via get_account
    email, acc = config.get_account("alice@alpeware.com")
    assert email == "alice@alpeware.com"
    assert acc.alias is None
    assert acc.auth_type == "service_account"
    assert acc.key_file == "/etc/gsuite/alpeware-sa.json"
    assert acc.subject == "alice@alpeware.com"
    assert acc.impersonate is True
    assert acc.scopes == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert acc.labels == ["work", "dwd"]
    assert acc.created_at == "2026-10-30T10:00:00Z"
    assert acc.resolved_subject("alice@alpeware.com") == "alice@alpeware.com"
    assert acc.resolved_key_path("alice@alpeware.com") == Path("/etc/gsuite/alpeware-sa.json")

    # Case-insensitive domain matching
    email_upper, acc_upper = config.get_account("Bob@ALPEWARE.COM")
    assert email_upper == "Bob@ALPEWARE.COM"
    assert acc_upper.subject == "Bob@ALPEWARE.COM"
    assert acc_upper.auth_type == "service_account"

    # 2. Wildcard resolution via resolve_targets
    targets = config.resolve_targets(account="alice@alpeware.com")
    assert len(targets) == 1
    assert targets[0][0] == "alice@alpeware.com"
    assert targets[0][1].auth_type == "service_account"
    assert targets[0][1].key_file == "/etc/gsuite/alpeware-sa.json"

    # 3. Explicit account precedence over domain wildcard
    config.accounts["alice@alpeware.com"] = AccountConfig(
        alias="alice-oauth",
        auth_type="oauth",
        token_file="/tokens/alice.json",
    )
    explicit_email, explicit_acc = config.get_account("alice@alpeware.com")
    assert explicit_email == "alice@alpeware.com"
    assert explicit_acc.auth_type == "oauth"
    assert explicit_acc.alias == "alice-oauth"

    resolved_targets = config.resolve_targets(account="alice@alpeware.com")
    assert len(resolved_targets) == 1
    assert resolved_targets[0][1].auth_type == "oauth"
    assert resolved_targets[0][1].alias == "alice-oauth"

    # Other domain users still resolve via wildcard
    _, other_acc = config.get_account("carol@alpeware.com")
    assert other_acc.auth_type == "service_account"

    # 4. Unknown domain raises TargetingError with available_domains in details
    with pytest.raises(TargetingError) as exc_info:
        config.get_account("david@unknown.org")
    assert "not found" in str(exc_info.value)
    assert "available_domains" in exc_info.value.details
    assert "alpeware.com" in exc_info.value.details["available_domains"]
