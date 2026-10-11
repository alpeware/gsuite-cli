"""Configuration management for gsuite-cli."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from gsuite_cli.exceptions import ConfigError, TargetingError

CONFIG_DIR = Path.home() / ".config" / "gsuite"
CONFIG_FILE = CONFIG_DIR / "config.json"
CLIENT_SECRET_FILE = CONFIG_DIR / "client_secret.json"
TOKENS_DIR = CONFIG_DIR / "tokens"


class AccountConfig(BaseModel):
    """Configuration for an individual Google account."""

    alias: str | None = None
    labels: list[str] = Field(default_factory=list)
    token_file: str | None = None
    scopes: list[str] = Field(default_factory=list)
    created_at: str | None = None

    def resolved_token_path(self, email: str) -> Path:
        """Return the fully expanded path to the token file."""
        if self.token_file:
            return Path(os.path.expanduser(self.token_file))
        return TOKENS_DIR / f"{email}.json"


class GSuiteSettings(BaseModel):
    """Global CLI settings."""

    output_format: str = "auto"
    timeout_seconds: int = 30
    max_results_default: int = 20
    concurrency_limit: int = 5


class GSuiteConfig(BaseModel):
    """Root configuration object stored in ~/.config/gsuite/config.json."""

    version: str = "1.0"
    default_account: str | None = None
    accounts: dict[str, AccountConfig] = Field(default_factory=dict)
    settings: GSuiteSettings = Field(default_factory=GSuiteSettings)

    def find_account_by_alias(self, alias: str) -> tuple[str, AccountConfig] | None:
        """Find an account by its alias."""
        for email, account in self.accounts.items():
            if account.alias and account.alias.lower() == alias.lower():
                return email, account
        return None

    def get_account(self, identifier: str) -> tuple[str, AccountConfig]:
        """Lookup an account by email or alias. Raises TargetingError if not found."""
        if identifier in self.accounts:
            return identifier, self.accounts[identifier]

        by_alias = self.find_account_by_alias(identifier)
        if by_alias:
            return by_alias

        known = list(self.accounts.keys())
        raise TargetingError(
            f"Account '{identifier}' not found in configuration.",
            details={"requested": identifier, "available_accounts": known},
        )

    def resolve_targets(
        self,
        account: str | None = None,
        label: str | None = None,
        all_accounts: bool = False,
    ) -> list[tuple[str, AccountConfig]]:
        """Resolve command targets based on account, label, all, or default_account.

        Returns a list of (email, AccountConfig) tuples.
        """
        # Flag mutual exclusion / priority
        if account:
            return [self.get_account(account)]

        if label:
            matching = [
                (email, acc)
                for email, acc in self.accounts.items()
                if label.lower() in [lbl.lower() for lbl in acc.labels]
            ]
            if not matching:
                all_labels = set()
                for acc in self.accounts.values():
                    all_labels.update(acc.labels)
                raise TargetingError(
                    f"No accounts found with label '{label}'.",
                    details={"label": label, "available_labels": sorted(list(all_labels))},
                )
            return matching

        if all_accounts:
            if not self.accounts:
                raise TargetingError("No accounts configured yet. Run 'gsuite auth add <email>'.")
            return list(self.accounts.items())

        # Fallback to default_account
        if self.default_account:
            if self.default_account in self.accounts:
                return [(self.default_account, self.accounts[self.default_account])]
            raise TargetingError(
                f"Configured default account '{self.default_account}' is not in accounts list."
            )

        # If only one account exists, use it as implicit default
        if len(self.accounts) == 1:
            email, acc = next(iter(self.accounts.items()))
            return [(email, acc)]

        if not self.accounts:
            raise TargetingError("No accounts configured. Run 'gsuite auth add <email>'.")

        raise TargetingError(
            "Multiple accounts configured but no target specified and no default_account set. "
            "Use --account, --label, --all, or set a default via 'gsuite auth default <email>'."
        )


def ensure_config_dir() -> Path:
    """Ensure ~/.config/gsuite and tokens directory exist with secure permissions (0700)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
        os.chmod(TOKENS_DIR, 0o700)
    except OSError:
        pass
    return CONFIG_DIR


def load_config() -> GSuiteConfig:
    """Load ~/.config/gsuite/config.json or return a fresh default instance."""
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        return GSuiteConfig()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GSuiteConfig.model_validate(data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Corrupt JSON in {CONFIG_FILE}: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to load {CONFIG_FILE}: {e}")


def save_config(config: GSuiteConfig) -> None:
    """Atomically save configuration to ~/.config/gsuite/config.json with 0600 permissions."""
    ensure_config_dir()
    payload = config.model_dump(mode="json")
    json_bytes = json.dumps(payload, indent=2).encode("utf-8")

    # Atomic write via temporary file in the same directory
    with tempfile.NamedTemporaryFile("wb", dir=CONFIG_DIR, delete=False) as tf:
        tf.write(json_bytes)
        temp_name = tf.name

    try:
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, CONFIG_FILE)
    except Exception as e:
        if os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        raise ConfigError(f"Failed to save configuration to {CONFIG_FILE}: {e}")
