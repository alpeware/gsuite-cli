"""CLI commands for installing and managing Google Antigravity skills."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import click

from gsuite_cli.commands.common import GSuiteCommand, GSuiteGroup
from gsuite_cli.formatters import console, print_json, render_error, render_success


def find_workspace_root(start_dir: Path | None = None) -> Path:
    """Find the root directory of the workspace by looking for .git or .agents markers."""
    curr = (start_dir or Path.cwd()).resolve()
    for parent in [curr, *curr.parents]:
        if (parent / ".git").exists() or (parent / ".agents").exists():
            return parent
    return curr


def find_skill_source(skill_name: str = "gsuite") -> Path:
    """Locate the source directory of the skill."""
    workspace_root = find_workspace_root()

    candidate_paths = [
        workspace_root / ".agents" / "skills" / skill_name,
        Path.cwd().resolve() / ".agents" / "skills" / skill_name,
        Path(__file__).resolve().parent.parent / "skills" / skill_name,
    ]

    for p in candidate_paths:
        if p.exists() and p.is_dir() and (p / "SKILL.md").exists():
            return p.resolve()

    raise FileNotFoundError(
        f"Could not locate skill source for '{skill_name}' containing SKILL.md. "
        f"Searched: {[str(p) for p in candidate_paths]}"
    )


def install_skill_files(
    skill_name: str,
    source_dir: Path,
    target_dir: Path,
) -> list[str]:
    """Copy all files from skill source directory to target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[str] = []

    for root, _, files in os.walk(source_dir):
        rel_root = Path(root).relative_to(source_dir)
        dest_root = target_dir / rel_root
        dest_root.mkdir(parents=True, exist_ok=True)

        for file_name in files:
            src_file = Path(root) / file_name
            dest_file = dest_root / file_name
            if src_file.resolve() != dest_file.resolve():
                shutil.copy2(src_file, dest_file)
            rel_file_path = str(rel_root / file_name) if str(rel_root) != "." else file_name
            copied_files.append(rel_file_path)

    return sorted(copied_files)


@click.group(name="skill", cls=GSuiteGroup)
def skill_group() -> None:
    """Manage Antigravity progressive skills."""


@click.command(name="install", cls=GSuiteCommand)
@click.option(
    "--global",
    "-g",
    "is_global",
    is_flag=True,
    help="Install globally to ~/.gemini/antigravity-cli/skills/<skill-folder>/",
)
@click.option(
    "--local",
    "-l",
    "is_local",
    is_flag=True,
    help="Install locally to <workspace-root>/.agents/skills/<skill-folder>/",
)
@click.option(
    "--dest",
    "-d",
    type=click.Path(path_type=Path),
    help="Install to a custom destination directory",
)
@click.option(
    "--skill",
    default="gsuite",
    help="Name of skill folder to install (default: 'gsuite')",
)
@click.pass_context
def install_skill_cmd(
    ctx: click.Context,
    is_global: bool,
    is_local: bool,
    dest: Path | None,
    skill: str,
) -> None:
    """Install the Antigravity progressive skill locally or globally.

    Default is local install (<workspace-root>/.agents/skills/<skill-folder>/) if neither flag is specified.
    """
    is_json = ctx.obj.get("json", False) if ctx.obj else False

    try:
        source_path = find_skill_source(skill)
    except FileNotFoundError as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    workspace_root = find_workspace_root()
    global_target = Path.home() / ".gemini" / "antigravity-cli" / "skills" / skill
    local_target = workspace_root / ".agents" / "skills" / skill

    targets: list[tuple[str, Path]] = []
    if dest:
        targets.append(("custom", dest.expanduser().resolve()))
    else:
        if is_global:
            targets.append(("global", global_target))
        if is_local:
            targets.append(("local", local_target))
        if not is_global and not is_local:
            # Default to local install
            targets.append(("local", local_target))

    results: list[dict[str, Any]] = []
    for scope_type, target_path in targets:
        try:
            copied = install_skill_files(skill, source_path, target_path)
            results.append({
                "scope": scope_type,
                "target": str(target_path),
                "files": copied,
                "status": "success",
            })
        except Exception as e:
            results.append({
                "scope": scope_type,
                "target": str(target_path),
                "error": str(e),
                "status": "error",
            })

    has_error = any(r["status"] == "error" for r in results)

    if is_json:
        print_json({
            "status": "error" if has_error else "success",
            "skill": skill,
            "source": str(source_path),
            "installations": results,
        })
    else:
        if has_error:
            for r in results:
                if r["status"] == "error":
                    render_error(f"Failed to install to {r['target']}: {r.get('error')}")
                else:
                    render_success(f"Installed to ({r['scope']}) {r['target']}")
        else:
            render_success(f"Antigravity skill '{skill}' installed successfully!")
            for r in results:
                console.print(f"  [bold cyan]• ({r['scope']})[/bold cyan] {r['target']}")
                console.print(f"    [dim]Files: {', '.join(r['files'])}[/dim]")
            console.print("\n[dim]Antigravity CLI will discover this skill automatically via progressive disclosure.[/dim]")

    if has_error:
        ctx.exit(1)


# Register install under skill_group
skill_group.add_command(install_skill_cmd)
