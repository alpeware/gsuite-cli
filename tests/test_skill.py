"""Unit tests for Antigravity skill installation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from gsuite_cli.commands.skill_cmd import (
    find_skill_source,
    find_workspace_root,
    install_skill_files,
)
from gsuite_cli.main import cli


def test_find_workspace_root(tmp_path: Path) -> None:
    # Test directory with .git
    repo_dir = tmp_path / "my_project"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    sub_dir = repo_dir / "src" / "pkg"
    sub_dir.mkdir(parents=True)

    root = find_workspace_root(sub_dir)
    assert root == repo_dir


def test_find_skill_source() -> None:
    source = find_skill_source("gsuite")
    assert source.exists()
    assert (source / "SKILL.md").exists()


def test_install_skill_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source_skill"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("dummy skill", encoding="utf-8")
    sub = source_dir / "scripts"
    sub.mkdir()
    (sub / "run.sh").write_text("echo hello", encoding="utf-8")

    dest_dir = tmp_path / "target_skill"
    copied = install_skill_files("gsuite", source_dir, dest_dir)

    assert "SKILL.md" in copied
    assert "scripts/run.sh" in copied
    assert (dest_dir / "SKILL.md").read_text(encoding="utf-8") == "dummy skill"
    assert (dest_dir / "scripts" / "run.sh").read_text(encoding="utf-8") == "echo hello"


def test_cli_skill_install_dest(tmp_path: Path) -> None:
    runner = CliRunner()
    dest = tmp_path / "custom_dest"
    result = runner.invoke(cli, ["skill", "install", "--dest", str(dest), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert (dest / "SKILL.md").exists()


def test_cli_skill_install_global(tmp_path: Path) -> None:
    runner = CliRunner()
    fake_home = tmp_path / "home"
    with patch("pathlib.Path.home", return_value=fake_home):
        result = runner.invoke(cli, ["skill", "install", "--global", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        expected_skill = fake_home / ".gemini" / "antigravity-cli" / "skills" / "gsuite" / "SKILL.md"
        assert expected_skill.exists()


def test_cli_skill_install_local(tmp_path: Path) -> None:
    runner = CliRunner()
    fake_workspace = tmp_path / "workspace"
    fake_workspace.mkdir()
    (fake_workspace / ".git").mkdir()

    with patch("gsuite_cli.commands.skill_cmd.find_workspace_root", return_value=fake_workspace):
        result = runner.invoke(cli, ["skill", "install", "--local", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        expected_skill = fake_workspace / ".agents" / "skills" / "gsuite" / "SKILL.md"
        assert expected_skill.exists()


def test_cli_install_skill_alias(tmp_path: Path) -> None:
    runner = CliRunner()
    dest = tmp_path / "alias_dest"
    result = runner.invoke(cli, ["install-skill", "--dest", str(dest)])
    assert result.exit_code == 0
    assert "installed successfully" in result.output
    assert (dest / "SKILL.md").exists()
