"""Unit tests for listing accounts with tags."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gsuite_cli.config import GSuiteConfig, save_config
from gsuite_cli.main import cli


def test_accounts_list_empty(mock_config_dir: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["accounts", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["count"] == 0
    assert data["accounts"] == []


def test_accounts_list_human(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()

    # Invoke 'gsuite accounts' (default list without subcommand)
    result = runner.invoke(cli, ["accounts"])
    assert result.exit_code == 0
    assert "Available Google Accounts & Tags" in result.output
    assert "alpeware@gmail.com" in result.output
    assert "#personal" in result.output
    assert "#alpeware" in result.output

    # Invoke 'gsuite accounts list'
    res_list = runner.invoke(cli, ["accounts", "list"])
    assert res_list.exit_code == 0
    assert "Available Google Accounts & Tags" in res_list.output
    assert "root@alpeware.com" in res_list.output
    assert "#work" in res_list.output


def test_accounts_list_json(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["accounts", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["count"] == 3
    assert data["default_account"] == "alpeware@gmail.com"

    accounts_by_email = {a["email"]: a for a in data["accounts"]}
    assert "alpeware@gmail.com" in accounts_by_email
    alpeware = accounts_by_email["alpeware@gmail.com"]
    assert alpeware["default"] is True
    assert "personal" in alpeware["tags"]
    assert "alpeware" in alpeware["tags"]
    assert "primary" in alpeware["tags"]

    work_acc = accounts_by_email["root@alpeware.com"]
    assert work_acc["alias"] == "work"
    assert work_acc["default"] is False
    assert "enterprise" in work_acc["tags"]


def test_accounts_filter_by_tag(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()

    # Filter with --tag on accounts list (matching work)
    res_work = runner.invoke(cli, ["accounts", "list", "--tag", "work", "--json"])
    assert res_work.exit_code == 0
    data_work = json.loads(res_work.output)
    assert data_work["count"] == 2
    emails = [a["email"] for a in data_work["accounts"]]
    assert "root@alpeware.com" in emails
    assert "foundation@nonprofit.org" in emails
    assert "alpeware@gmail.com" not in emails

    # Filter with --label
    res_personal = runner.invoke(cli, ["accounts", "list", "--label", "personal", "--json"])
    assert res_personal.exit_code == 0
    data_personal = json.loads(res_personal.output)
    assert data_personal["count"] == 1
    assert data_personal["accounts"][0]["email"] == "alpeware@gmail.com"

    # Filter on group level: gsuite accounts --tag work
    res_group = runner.invoke(cli, ["accounts", "--tag", "work", "--json"])
    assert res_group.exit_code == 0
    data_group = json.loads(res_group.output)
    assert data_group["count"] == 2


def test_accounts_filter_nonexistent(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["accounts", "list", "--tag", "nonexistent"])
    assert result.exit_code == 0
    assert "No accounts found with tag 'nonexistent'" in result.output


def test_auth_accounts_alias(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "accounts", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["count"] == 3


def test_auth_tags_alias(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "tags", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert "work" in data["labels"]
