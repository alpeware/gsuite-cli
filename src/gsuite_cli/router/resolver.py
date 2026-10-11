"""Target resolver for commands based on --account, --label, --all, or defaults."""

from __future__ import annotations

from gsuite_cli.config import AccountConfig, GSuiteConfig, load_config


def resolve_command_targets(
    config: GSuiteConfig | None = None,
    account: str | None = None,
    label: str | None = None,
    all_accounts: bool = False,
) -> list[tuple[str, AccountConfig]]:
    """Resolve which accounts to target.

    Precedence:
    1. --account <email|alias>
    2. --label <label>
    3. --all
    4. config.default_account (or single registered account)
    """
    cfg = config or load_config()
    return cfg.resolve_targets(account=account, label=label, all_accounts=all_accounts)
