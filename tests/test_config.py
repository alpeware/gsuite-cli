"""Tests for configuration parsing, persistence, and target resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from gsuite_cli.config import (
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
