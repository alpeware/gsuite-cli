"""Tests for targeting router and concurrent executor."""

from __future__ import annotations

from gsuite_cli.config import AccountConfig, GSuiteConfig
from gsuite_cli.exceptions import GSuiteError
from gsuite_cli.router.executor import (
    execute_across_targets,
)


def test_single_account_execution_success(sample_config: GSuiteConfig) -> None:
    targets = [sample_config.get_account("personal")]

    def dummy_action(email: str, acc: AccountConfig) -> dict[str, str]:
        return {"result": f"hello {email}"}

    res = execute_across_targets(targets, dummy_action)
    assert res.is_single
    assert res.all_succeeded

    payload = res.to_dict()
    assert payload["status"] == "success"
    assert payload["account"] == "alpeware@gmail.com"
    assert payload["result"] == "hello alpeware@gmail.com"


def test_single_account_execution_failure(sample_config: GSuiteConfig) -> None:
    targets = [sample_config.get_account("personal")]

    def failing_action(email: str, acc: AccountConfig) -> None:
        raise GSuiteError("API error occurred", code="API_FAILURE")

    res = execute_across_targets(targets, failing_action)
    assert res.is_single
    assert not res.all_succeeded

    payload = res.to_dict()
    assert payload["status"] == "error"
    assert payload["error_code"] == "API_FAILURE"


def test_multi_account_fault_isolation(sample_config: GSuiteConfig) -> None:
    targets = sample_config.resolve_targets(label="work")
    assert len(targets) == 2

    # Account root@alpeware.com succeeds, foundation@nonprofit.org fails
    def partial_action(email: str, acc: AccountConfig) -> str:
        if email == "foundation@nonprofit.org":
            raise GSuiteError("Rate limit hit", code="RATE_LIMITED")
        return "data_ok"

    res = execute_across_targets(targets, partial_action)
    assert not res.is_single
    assert res.any_succeeded
    assert not res.all_succeeded

    payload = res.to_dict()
    assert payload["status"] == "partial_success"
    assert payload["targeted_accounts"] == 2
    assert payload["succeeded_accounts"] == 1
    assert payload["failed_accounts"] == 1

    accounts = payload["accounts"]
    assert accounts["root@alpeware.com"]["status"] == "success"
    assert accounts["foundation@nonprofit.org"]["status"] == "error"
    assert accounts["foundation@nonprofit.org"]["error_code"] == "RATE_LIMITED"


def test_all_accounts_parallel_execution(sample_config: GSuiteConfig) -> None:
    targets = sample_config.resolve_targets(all_accounts=True)
    assert len(targets) == 3

    def action(email: str, acc: AccountConfig) -> list[str]:
        return [f"msg_1_{email}", f"msg_2_{email}"]

    res = execute_across_targets(targets, action)
    assert res.all_succeeded

    payload = res.to_dict()
    assert payload["status"] == "success"
    assert payload["targeted_accounts"] == 3
    assert payload["total_items"] == 6
