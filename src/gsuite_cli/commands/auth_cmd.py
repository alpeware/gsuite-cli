"""CLI commands for managing authentication, accounts, and labels."""

from __future__ import annotations

import datetime
from typing import Any

import click

from gsuite_cli.auth import (
    authenticate_account,
    delete_credentials,
    get_client_secret_path,
    load_credentials,
    resolve_scopes,
    save_credentials,
)
from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import AccountConfig, load_config, save_config
from gsuite_cli.exceptions import ConfigError, GSuiteError
from gsuite_cli.formatters import (
    console,
    print_json,
    render_accounts_table,
    render_error,
    render_success,
)


@click.group(name="auth", cls=GSuiteGroup)
def auth_group() -> None:
    """Manage Google Workspace & Gmail account credentials and labels."""


@auth_group.command(name="add")
@click.argument("email", required=True)
@click.option("--alias", help="Short mnemonic name for account (e.g. 'work', 'personal')")
@click.option("--labels", help="Comma-separated labels (e.g. 'work,alpeware,primary')")
@click.option("--headless", is_flag=True, help="Force headless out-of-band auth for SSH/Termux")
@click.option(
    "--scopes",
    default="standard",
    help="Scope profile ('read-only', 'standard', 'full') or comma-separated scope URLs",
)
@click.pass_context
def auth_add(
    ctx: click.Context,
    email: str,
    alias: str | None,
    labels: str | None,
    headless: bool,
    scopes: str,
) -> None:
    """Register and authenticate a Google account."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    resolved_scopes = resolve_scopes(scopes)
    config = load_config()

    try:
        secret_path = get_client_secret_path()
    except ConfigError as e:
        if is_json:
            print_json(
                {
                    "status": "error",
                    "error_code": e.code,
                    "message": e.message,
                    "details": e.details,
                }
            )
        else:
            render_error(e.message, e.details)
        ctx.exit(1)

    if not is_json:
        console.print(f"[bold cyan]Authenticating account:[/bold cyan] {email}")
        console.print(f"[dim]Using scopes profile: {scopes}[/dim]")

    try:
        creds = authenticate_account(
            email=email,
            scopes=resolved_scopes,
            headless=headless,
            client_secret_path=secret_path,
        )
        token_path = save_credentials(email, creds)
    except Exception as e:
        if is_json:
            err_dict = (
                e.to_dict()
                if isinstance(e, GSuiteError)
                else {"error_code": "AUTH_FAILED", "message": str(e)}
            )
            print_json({"status": "error", **err_dict})
        else:
            render_error(f"Authentication failed for {email}: {e}")
        ctx.exit(1)

    # Parse and update config
    label_list = [lbl.strip().lower() for lbl in labels.split(",") if lbl.strip()] if labels else []
    acc_config = AccountConfig(
        alias=alias,
        labels=label_list,
        token_file=str(token_path),
        scopes=resolved_scopes,
        created_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
    config.accounts[email] = acc_config

    # If first account added, automatically set as default_account
    if not config.default_account:
        config.default_account = email

    save_config(config)

    if is_json:
        print_json(
            {
                "status": "success",
                "account": email,
                "alias": alias,
                "labels": label_list,
                "default": config.default_account == email,
                "token_file": str(token_path),
            }
        )
    else:
        render_success(f"Successfully authenticated and registered '{email}'!")
        if config.default_account == email:
            console.print("  [bold yellow]★[/bold yellow] Set as active default account.")


@auth_group.command(name="list")
@click.pass_context
def auth_list(ctx: click.Context) -> None:
    """List all registered accounts, aliases, labels, and token health."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    if not config.accounts:
        if is_json:
            print_json({"status": "success", "count": 0, "accounts": {}, "default_account": None})
        else:
            console.print(
                "[yellow]No accounts registered yet.[/yellow] Run 'gsuite auth add <email>' to get started."
            )
        return

    statuses: dict[str, dict[str, Any]] = {}
    for email, acc in config.accounts.items():
        try:
            creds = load_credentials(email, custom_path=acc.token_file, auto_refresh=False)
            statuses[email] = {
                "valid": creds.valid,
                "expired": creds.expired,
                "has_refresh_token": bool(creds.refresh_token),
            }
        except Exception as e:
            statuses[email] = {
                "valid": False,
                "expired": True,
                "error": str(e),
            }

    if is_json:
        acc_payload = {}
        for email, acc in config.accounts.items():
            st = statuses.get(email, {})
            acc_payload[email] = {
                "alias": acc.alias,
                "labels": acc.labels,
                "is_default": email == config.default_account,
                "token_file": acc.token_file,
                "scopes_count": len(acc.scopes),
                "status": st,
            }
        print_json(
            {
                "status": "success",
                "count": len(config.accounts),
                "default_account": config.default_account,
                "accounts": acc_payload,
            }
        )
    else:
        render_accounts_table(config.accounts, config.default_account, statuses)


@auth_group.command(name="remove")
@click.argument("identifier", required=True)
@click.pass_context
def auth_remove(ctx: click.Context, identifier: str) -> None:
    """Remove an account and delete its local token file."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        email, acc = config.get_account(identifier)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    delete_credentials(email, custom_path=acc.token_file)
    del config.accounts[email]

    if config.default_account == email:
        config.default_account = next(iter(config.accounts.keys())) if config.accounts else None

    save_config(config)

    if is_json:
        print_json(
            {"status": "success", "removed_account": email, "new_default": config.default_account}
        )
    else:
        render_success(f"Removed account '{email}' and deleted its credentials.")


@auth_group.command(name="default")
@click.argument("identifier", required=True)
@click.pass_context
def auth_default(ctx: click.Context, identifier: str) -> None:
    """Set the fallback default account."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        email, _ = config.get_account(identifier)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    config.default_account = email
    save_config(config)

    if is_json:
        print_json({"status": "success", "default_account": email})
    else:
        render_success(f"Default account set to '{email}'.")


@auth_group.command(name="test")
@click.option("--account", "-a", help="Target account (email or alias)")
@click.option("--label", "-l", help="Target all accounts matching label")
@click.option("--all", "all_accounts", is_flag=True, help="Test all registered accounts")
@click.pass_context
def auth_test(
    ctx: click.Context, account: str | None, label: str | None, all_accounts: bool
) -> None:
    """Test token validity and refresh status across accounts."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    try:
        targets = config.resolve_targets(account=account, label=label, all_accounts=all_accounts)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    results: dict[str, Any] = {}
    for email, acc in targets:
        try:
            creds = load_credentials(email, custom_path=acc.token_file, auto_refresh=True)
            results[email] = {
                "status": "ok",
                "valid": creds.valid,
                "has_refresh_token": bool(creds.refresh_token),
            }
        except Exception as e:
            results[email] = {
                "status": "error",
                "error": str(e),
            }

    if is_json:
        print_json({"status": "success", "accounts": results})
    else:
        for email, res in results.items():
            if res.get("status") == "ok":
                render_success(f"Account '{email}': Token healthy & validated.")
            else:
                render_error(f"Account '{email}': {res.get('error')}")


@auth_group.group(name="labels", cls=GSuiteGroup)
def labels_group() -> None:
    """Manage account labels."""


@labels_group.command(name="add")
@click.argument("identifier", required=True)
@click.argument("label", required=True)
@click.pass_context
def labels_add(ctx: click.Context, identifier: str, label: str) -> None:
    """Add a label to an account."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()
    email, acc = config.get_account(identifier)

    label_clean = label.strip().lower()
    if label_clean not in acc.labels:
        acc.labels.append(label_clean)
        save_config(config)

    if is_json:
        print_json({"status": "success", "account": email, "labels": acc.labels})
    else:
        render_success(
            f"Added label '{label_clean}' to '{email}'. Current labels: {', '.join(acc.labels)}"
        )


@labels_group.command(name="remove")
@click.argument("identifier", required=True)
@click.argument("label", required=True)
@click.pass_context
def labels_remove(ctx: click.Context, identifier: str, label: str) -> None:
    """Remove a label from an account."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()
    email, acc = config.get_account(identifier)

    label_clean = label.strip().lower()
    if label_clean in acc.labels:
        acc.labels.remove(label_clean)
        save_config(config)

    if is_json:
        print_json({"status": "success", "account": email, "labels": acc.labels})
    else:
        render_success(
            f"Removed label '{label_clean}' from '{email}'. Current labels: {', '.join(acc.labels)}"
        )


@labels_group.command(name="list")
@click.pass_context
def labels_list(ctx: click.Context) -> None:
    """List all known labels and the accounts assigned to each."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    label_map: dict[str, list[str]] = {}
    for email, acc in config.accounts.items():
        for lbl in acc.labels:
            label_map.setdefault(lbl, []).append(email)

    if is_json:
        print_json({"status": "success", "labels": label_map})
    else:
        if not label_map:
            console.print("[yellow]No labels defined yet.[/yellow]")
            return
        for lbl, accounts in sorted(label_map.items()):
            console.print(f"[bold green]• {lbl}:[/bold green] {', '.join(accounts)}")
