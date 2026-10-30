"""CLI commands for managing authentication, accounts, and labels."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from gsuite_cli.auth import (
    authenticate_account,
    copy_service_account_key,
    delete_credentials,
    delete_service_account_key,
    get_client_secret_path,
    get_dwd_setup_info,
    load_account_credentials,
    load_sa_credentials,
    resolve_scopes,
    save_credentials,
)
from gsuite_cli.commands.accounts_cmd import accounts_list
from gsuite_cli.commands.common import GSuiteGroup
from gsuite_cli.config import AccountConfig, DomainConfig, load_config, save_config
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
@click.option(
    "--labels",
    "--tags",
    help="Comma-separated labels or tags (e.g. 'work,alpeware,primary')",
)
@click.option("--headless", is_flag=True, help="Force headless out-of-band auth for SSH/Termux")
@click.option(
    "--scopes",
    default="standard",
    help="Scope profile ('read-only', 'standard', 'full') or comma-separated scope URLs",
)
@click.option(
    "--service-account",
    "--key-file",
    "service_account_key",
    type=click.Path(path_type=Path),
    help="Path to Service Account JSON key file (uses Service Account / DWD instead of OAuth)",
)
@click.option(
    "--subject",
    help="Workspace user email to impersonate via Domain-Wide Delegation (defaults to EMAIL)",
)
@click.option(
    "--no-impersonate",
    is_flag=True,
    default=False,
    help="Authenticate as the raw service account without user impersonation",
)
@click.option(
    "--no-verify",
    is_flag=True,
    default=False,
    help="Skip immediate live token refresh check when registering a service account",
)
@click.pass_context
def auth_add(
    ctx: click.Context,
    email: str,
    alias: str | None,
    labels: str | None,
    headless: bool,
    scopes: str,
    service_account_key: Path | None = None,
    subject: str | None = None,
    no_impersonate: bool = False,
    no_verify: bool = False,
) -> None:
    """Register and authenticate a Google account."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    resolved_scopes = resolve_scopes(scopes)
    label_list = [lbl.strip().lower() for lbl in labels.split(",") if lbl.strip()] if labels else []
    config = load_config()

    if service_account_key:
        if not is_json:
            console.print(f"[bold cyan]Registering service account:[/bold cyan] {email}")
            console.print(f"[dim]Using scopes profile: {scopes}[/dim]")

        impersonate = not no_impersonate
        resolved_subject = None if no_impersonate else (subject or email)

        try:
            key_path = copy_service_account_key(service_account_key, email)
            load_sa_credentials(
                key_path,
                scopes=resolved_scopes,
                subject=resolved_subject,
                verify_refresh=not no_verify,
            )
        except Exception as e:
            if is_json:
                err_dict = (
                    e.to_dict()
                    if isinstance(e, GSuiteError)
                    else {"error_code": "AUTH_FAILED", "message": str(e)}
                )
                print_json({"status": "error", **err_dict})
            else:
                render_error(f"Service account registration failed for {email}: {e}")
            ctx.exit(1)

        acc_config = AccountConfig(
            alias=alias,
            labels=label_list,
            auth_type="service_account",
            key_file=str(key_path),
            subject=subject,
            impersonate=impersonate,
            scopes=resolved_scopes,
            created_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )
        config.accounts[email] = acc_config

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
                    "auth_type": "service_account",
                    "key_file": str(key_path),
                    "subject": resolved_subject,
                    "impersonate": impersonate,
                }
            )
        else:
            if impersonate:
                render_success(
                    f"Successfully registered '{email}' with Domain-Wide Delegation (impersonating '{resolved_subject}')!"
                )
            else:
                render_success(f"Successfully registered raw service account '{email}'!")
            if config.default_account == email:
                console.print("  [bold yellow]★[/bold yellow] Set as active default account.")
        return

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
                "auth_type": "oauth",
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

    if not config.accounts and not config.domains:
        if is_json:
            print_json(
                {
                    "status": "success",
                    "count": 0,
                    "accounts": {},
                    "domains": {},
                    "default_account": None,
                }
            )
        else:
            console.print(
                "[yellow]No accounts registered yet.[/yellow] Run 'gsuite auth add <email>' to get started."
            )
        return

    statuses: dict[str, dict[str, Any]] = {}
    for email, acc in config.accounts.items():
        try:
            creds = load_account_credentials(email, account_config=acc, auto_refresh=False)
            if acc.auth_type == "service_account":
                statuses[email] = {
                    "valid": True,
                    "expired": False,
                    "auth_type": "service_account",
                    "subject": acc.resolved_subject(email),
                }
            else:
                statuses[email] = {
                    "valid": creds.valid,
                    "expired": creds.expired,
                    "has_refresh_token": bool(getattr(creds, "refresh_token", None)),
                    "auth_type": "oauth",
                }
        except Exception as e:
            statuses[email] = {
                "valid": False,
                "expired": True,
                "auth_type": acc.auth_type,
                "error": str(e),
            }

    if is_json:
        acc_payload = {}
        for email, acc in config.accounts.items():
            st = statuses.get(email, {})
            acc_payload[email] = {
                "alias": acc.alias,
                "labels": acc.labels,
                "auth_type": acc.auth_type,
                "is_default": email == config.default_account,
                "token_file": acc.token_file,
                "key_file": acc.key_file,
                "subject": acc.resolved_subject(email),
                "scopes_count": len(acc.scopes),
                "status": st,
            }
        print_json(
            {
                "status": "success",
                "count": len(config.accounts),
                "default_account": config.default_account,
                "accounts": acc_payload,
                "domains": {k: v.model_dump() for k, v in config.domains.items()},
            }
        )
    else:
        if config.accounts:
            render_accounts_table(config.accounts, config.default_account, statuses)
        if config.domains:
            console.print("\n[bold]Configured Wildcard Domains:[/bold]")
            table = Table(show_lines=True)
            table.add_column("Domain", style="cyan", no_wrap=True)
            table.add_column("Key File", style="dim")
            table.add_column("Labels", style="green")
            table.add_column("Scopes Count", style="blue")
            for dom, d_cfg in config.domains.items():
                labels_str = ", ".join(d_cfg.labels) if d_cfg.labels else "[dim]none[/dim]"
                table.add_row(dom, d_cfg.key_file, labels_str, str(len(d_cfg.scopes)))
            console.print(table)


@auth_group.command(name="remove")
@click.argument("identifier", required=True)
@click.pass_context
def auth_remove(ctx: click.Context, identifier: str) -> None:
    """Remove an account and delete its local token or key file."""
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

    if acc.auth_type == "service_account":
        del config.accounts[email]
        delete_service_account_key(email, custom_path=acc.key_file, config_obj=config)
    else:
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
        render_success(f"Removed account '{email}' and cleaned up its credentials.")


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
            creds = load_account_credentials(email, account_config=acc, auto_refresh=True)
            res_entry: dict[str, Any] = {
                "status": "ok",
                "valid": creds.valid,
                "has_refresh_token": bool(getattr(creds, "refresh_token", None)),
            }
            if acc.auth_type == "service_account":
                res_entry["auth_type"] = "service_account"
                res_entry["subject"] = acc.resolved_subject(email)
            results[email] = res_entry
        except Exception as e:
            results[email] = {
                "status": "error",
                "auth_type": acc.auth_type,
                "error": str(e),
            }

    if is_json:
        print_json({"status": "success", "accounts": results})
    else:
        for email, res in results.items():
            if res.get("status") == "ok":
                if res.get("auth_type") == "service_account":
                    render_success(f"Account '{email}' (Service Account): Credentials valid & verified.")
                else:
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


# ---------------------------------------------------------------------------
# Domain-Wide Delegation (DWD) & Wildcard Domain Commands
# ---------------------------------------------------------------------------

@auth_group.group(name="domain", cls=GSuiteGroup)
def domain_group() -> None:
    """Manage Google Workspace Domain-Wide Delegation wildcard domains."""


@domain_group.command(name="add")
@click.argument("domain", required=True)
@click.option(
    "--service-account",
    "--key-file",
    "service_account_key",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to Service Account JSON key file for Domain-Wide Delegation",
)
@click.option(
    "--scopes",
    default="standard",
    help="Scope profile ('read-only', 'standard', 'full') or comma-separated scope URLs",
)
@click.option(
    "--labels",
    "--tags",
    help="Comma-separated labels or tags (e.g. 'work,corp')",
)
@click.option(
    "--test-user",
    help="Workspace user email to immediately verify Domain-Wide Delegation token generation against",
)
@click.pass_context
def domain_add(
    ctx: click.Context,
    domain: str,
    service_account_key: Path,
    scopes: str,
    labels: str | None,
    test_user: str | None,
) -> None:
    """Register a Google Workspace domain for wildcard Domain-Wide Delegation."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    dom = domain.strip().lower().lstrip("@")
    resolved_scopes = resolve_scopes(scopes)
    label_list = [lbl.strip().lower() for lbl in labels.split(",") if lbl.strip()] if labels else []
    config = load_config()

    try:
        key_path = copy_service_account_key(service_account_key, f"domain_{dom}")
        dwd_info = get_dwd_setup_info(key_path, resolved_scopes)
        if test_user:
            load_sa_credentials(key_path, scopes=resolved_scopes, subject=test_user, verify_refresh=True)
    except Exception as e:
        if is_json:
            err_dict = (
                e.to_dict()
                if isinstance(e, GSuiteError)
                else {"error_code": "AUTH_FAILED", "message": str(e)}
            )
            print_json({"status": "error", **err_dict})
        else:
            render_error(f"Failed to register domain '{dom}': {e}")
        ctx.exit(1)

    dom_config = DomainConfig(
        domain=dom,
        key_file=str(key_path),
        scopes=resolved_scopes,
        labels=label_list,
        created_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
    config.domains[dom] = dom_config
    save_config(config)

    if is_json:
        print_json(
            {
                "status": "success",
                "domain": dom,
                "key_file": str(key_path),
                "labels": label_list,
                "scopes": resolved_scopes,
                "dwd_setup": dwd_info,
            }
        )
    else:
        render_success(f"Domain '{dom}' successfully registered with Domain-Wide Delegation!")
        console.print(f"  [bold cyan]Client ID:[/bold cyan]     {dwd_info['client_id']}")
        console.print(f"  [bold cyan]Client Email:[/bold cyan]  {dwd_info['client_email']}")
        console.print(f"  [bold cyan]Scopes (CSV):[/bold cyan]   {dwd_info['scopes_csv']}")


@domain_group.command(name="list")
@click.pass_context
def domain_list(ctx: click.Context) -> None:
    """List all registered wildcard domains."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()

    domains_payload = {k: v.model_dump() for k, v in config.domains.items()}
    if is_json:
        print_json(
            {
                "status": "success",
                "count": len(config.domains),
                "domains": domains_payload,
            }
        )
    else:
        if not config.domains:
            console.print(
                "[yellow]No wildcard domains registered yet.[/yellow] Run 'gsuite auth domain add <domain> --key-file <key.json>' to add one."
            )
            return

        table = Table(title="Configured Wildcard Domains", show_lines=True)
        table.add_column("Domain", style="cyan", no_wrap=True)
        table.add_column("Key File", style="dim")
        table.add_column("Labels", style="green")
        table.add_column("Scopes Count", style="blue")
        for dom, d_cfg in config.domains.items():
            labels_str = ", ".join(d_cfg.labels) if d_cfg.labels else "[dim]none[/dim]"
            table.add_row(dom, d_cfg.key_file, labels_str, str(len(d_cfg.scopes)))
        console.print(table)


@domain_group.command(name="info")
@click.argument("domain", required=True)
@click.pass_context
def domain_info(ctx: click.Context, domain: str) -> None:
    """Show Domain-Wide Delegation setup details for a registered domain."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()
    dom = domain.strip().lower().lstrip("@")

    dom_cfg = None
    for d_name, d_val in config.domains.items():
        if d_name.lower() == dom:
            dom_cfg = d_val
            break

    if not dom_cfg:
        msg = f"Domain '{domain}' is not registered."
        if is_json:
            print_json({"status": "error", "message": msg})
        else:
            render_error(msg)
        ctx.exit(1)

    try:
        dwd_info = get_dwd_setup_info(dom_cfg.resolved_key_path(), dom_cfg.scopes)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    if is_json:
        print_json(
            {
                "status": "success",
                "domain": dom,
                **dwd_info,
            }
        )
    else:
        render_success(f"Domain-Wide Delegation setup info for '{dom}':")
        console.print(f"  [bold cyan]Client ID:[/bold cyan]     {dwd_info['client_id']}")
        console.print(f"  [bold cyan]Client Email:[/bold cyan]  {dwd_info['client_email']}")
        console.print(f"  [bold cyan]Project ID:[/bold cyan]    {dwd_info.get('project_id', '')}")
        console.print(f"  [bold cyan]Scopes (CSV):[/bold cyan]   {dwd_info['scopes_csv']}")
        console.print("\n[dim]To authorize in Google Workspace Admin Console:[/dim]")
        console.print(
            "[dim]1. Go to Security > Access and data control > API controls > Domain-wide Delegation.[/dim]"
        )
        console.print(
            "[dim]2. Click 'Add new' and enter the Client ID and comma-separated Scopes above.[/dim]"
        )


@domain_group.command(name="remove")
@click.argument("domain", required=True)
@click.pass_context
def domain_remove(ctx: click.Context, domain: str) -> None:
    """Remove a registered wildcard domain and its key file."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    config = load_config()
    dom = domain.strip().lower().lstrip("@")

    matched_key = None
    for d_name in config.domains:
        if d_name.lower() == dom:
            matched_key = d_name
            break

    if not matched_key:
        msg = f"Domain '{domain}' is not registered."
        if is_json:
            print_json({"status": "error", "message": msg})
        else:
            render_error(msg)
        ctx.exit(1)

    dom_cfg = config.domains[matched_key]
    del config.domains[matched_key]
    delete_service_account_key(f"domain_{matched_key}", custom_path=dom_cfg.key_file, config_obj=config)
    save_config(config)

    if is_json:
        print_json({"status": "success", "removed_domain": matched_key})
    else:
        render_success(f"Removed domain '{matched_key}' and cleaned up credentials.")


@auth_group.command(name="dwd-info")
@click.option(
    "--service-account",
    "--key-file",
    "service_account_key",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to Service Account JSON key file",
)
@click.option(
    "--scopes",
    default="standard",
    help="Scope profile ('read-only', 'standard', 'full') or comma-separated scope URLs",
)
@click.pass_context
def auth_dwd_info(ctx: click.Context, service_account_key: Path, scopes: str) -> None:
    """Extract and display Google Workspace Domain-Wide Delegation setup info from a service account key."""
    is_json = ctx.obj.get("json", False) if ctx.obj else False
    resolved_scopes = resolve_scopes(scopes)

    try:
        dwd_info = get_dwd_setup_info(service_account_key, resolved_scopes)
    except Exception as e:
        if is_json:
            print_json({"status": "error", "message": str(e)})
        else:
            render_error(str(e))
        ctx.exit(1)

    if is_json:
        print_json({"status": "success", **dwd_info})
    else:
        render_success("Domain-Wide Delegation setup info:")
        console.print(f"  [bold cyan]Client ID:[/bold cyan]     {dwd_info['client_id']}")
        console.print(f"  [bold cyan]Client Email:[/bold cyan]  {dwd_info['client_email']}")
        console.print(f"  [bold cyan]Project ID:[/bold cyan]    {dwd_info.get('project_id', '')}")
        console.print(f"  [bold cyan]Scopes (CSV):[/bold cyan]   {dwd_info['scopes_csv']}")
        console.print("\n[dim]To authorize in Google Workspace Admin Console:[/dim]")
        console.print(
            "[dim]1. Go to Security > Access and data control > API controls > Domain-wide Delegation.[/dim]"
        )
        console.print(
            "[dim]2. Click 'Add new' and enter the Client ID and comma-separated Scopes above.[/dim]"
        )


# Aliases for tags and accounts under auth group
auth_group.add_command(labels_group, name="tags")
auth_group.add_command(accounts_list, name="accounts")
