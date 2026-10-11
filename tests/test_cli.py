"""Integration tests for CLI entrypoints using CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from gsuite_cli.config import GSuiteConfig, save_config
from gsuite_cli.main import cli


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "gsuite, version 0.1.0" in result.output


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Manage Google Workspace & Gmail" in result.output
    assert "gmail" in result.output
    assert "calendar" in result.output
    assert "drive" in result.output
    assert "docs" in result.output
    assert "sheets" in result.output


def test_cli_auth_list_empty(mock_config_dir: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["count"] == 0


def test_cli_auth_list_populated(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["count"] == 3
    assert "alpeware@gmail.com" in data["accounts"]


def test_cli_auth_labels_flow(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()

    # List labels
    res_list = runner.invoke(cli, ["auth", "labels", "list", "--json"])
    assert res_list.exit_code == 0
    labels_data = json.loads(res_list.output)
    assert "work" in labels_data["labels"]

    # Add label
    res_add = runner.invoke(cli, ["auth", "labels", "add", "personal", "finance", "--json"])
    assert res_add.exit_code == 0
    add_data = json.loads(res_add.output)
    assert "finance" in add_data["labels"]

    # Remove label
    res_rem = runner.invoke(cli, ["auth", "labels", "remove", "personal", "finance", "--json"])
    assert res_rem.exit_code == 0
    rem_data = json.loads(res_rem.output)
    assert "finance" not in rem_data["labels"]


def test_cli_gmail_search_json(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()

    mock_results = [
        {
            "id": "18f92b7c4d5e0123",
            "threadId": "18f92b7c4d5e0123",
            "from": "alerts@github.com",
            "to": "alpeware@gmail.com",
            "subject": "Security Alert",
            "date": "2026-10-11T08:00:00Z",
            "snippet": "Vulnerability alert...",
            "labels": ["INBOX", "UNREAD"],
        }
    ]

    with patch("gsuite_cli.commands.gmail_cmd.search_messages", return_value=mock_results):
        result = runner.invoke(cli, ["gmail", "search", "is:unread", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["account"] == "alpeware@gmail.com"
        assert len(data["data"]) == 1
        assert data["data"][0]["subject"] == "Security Alert"


def test_cli_calendar_agenda_json(mock_config_dir: Path, sample_config: GSuiteConfig) -> None:
    save_config(sample_config)
    runner = CliRunner()

    mock_events = [
        {
            "id": "ev_standup",
            "summary": "Morning Standup",
            "start": "2026-10-12T09:00:00Z",
            "end": "2026-10-12T09:30:00Z",
            "location": "Google Meet",
            "meet_link": "https://meet.google.com/xyz",
            "attendees": ["team@alpeware.com"],
        }
    ]

    with patch("gsuite_cli.commands.calendar_cmd.get_agenda", return_value=mock_events):
        result = runner.invoke(cli, ["calendar", "agenda", "--today", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert len(data["data"]) == 1
        assert data["data"][0]["summary"] == "Morning Standup"
