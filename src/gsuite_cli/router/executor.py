"""Concurrent multi-account execution engine with per-account fault isolation."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import Any

from gsuite_cli.config import AccountConfig
from gsuite_cli.exceptions import GSuiteError


class AccountResult:
    """Encapsulates the result of executing an action against a single account."""

    def __init__(
        self,
        email: str,
        success: bool,
        data: Any = None,
        error: GSuiteError | Exception | None = None,
    ):
        self.email = email
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        if self.success:
            return {
                "status": "success",
                "data": self.data,
            }
        error_dict: dict[str, Any] = {
            "status": "error",
            "message": str(self.error),
        }
        if isinstance(self.error, GSuiteError):
            error_dict["error_code"] = self.error.code
            if self.error.details:
                error_dict["details"] = self.error.details
        else:
            error_dict["error_code"] = "UNKNOWN_ERROR"
        return error_dict


class AggregatedResult:
    """Aggregated results across multiple accounts."""

    def __init__(self, targets: list[tuple[str, AccountConfig]], results: list[AccountResult]):
        self.targets = targets
        self.results = results

    @property
    def is_single(self) -> bool:
        return len(self.targets) == 1

    @property
    def single_result(self) -> AccountResult:
        if not self.results:
            raise RuntimeError("No results available.")
        return self.results[0]

    @property
    def all_succeeded(self) -> bool:
        return bool(self.results) and all(r.success for r in self.results)

    @property
    def any_succeeded(self) -> bool:
        return any(r.success for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        """Convert aggregated results into standard API/JSON response envelope."""
        if self.is_single:
            single = self.single_result
            if single.success:
                res: dict[str, Any] = {
                    "status": "success",
                    "account": single.email,
                }
                if isinstance(single.data, dict):
                    res.update(single.data)
                elif isinstance(single.data, list):
                    res["count"] = len(single.data)
                    res["data"] = single.data
                else:
                    res["data"] = single.data
                return res
            else:
                err_dict = single.to_dict()
                return {
                    "status": "error",
                    "account": single.email,
                    "error_code": err_dict.get("error_code", "ERROR"),
                    "message": err_dict.get("message", "An error occurred"),
                    "details": err_dict.get("details", {}),
                }

        # Multi-account envelope
        accounts_dict: dict[str, Any] = {}
        success_count = 0
        failure_count = 0
        total_items = 0

        for r in self.results:
            acc_entry = r.to_dict()
            accounts_dict[r.email] = acc_entry
            if r.success:
                success_count += 1
                if isinstance(r.data, list):
                    total_items += len(r.data)
                elif isinstance(r.data, dict) and "count" in r.data:
                    total_items += r.data["count"]
            else:
                failure_count += 1

        overall_status = "success"
        if failure_count > 0 and success_count > 0:
            overall_status = "partial_success"
        elif failure_count > 0 and success_count == 0:
            overall_status = "failure"

        return {
            "status": overall_status,
            "targeted_accounts": len(self.targets),
            "succeeded_accounts": success_count,
            "failed_accounts": failure_count,
            "total_items": total_items,
            "accounts": accounts_dict,
        }


def execute_across_targets(
    targets: list[tuple[str, AccountConfig]],
    action: Callable[[str, AccountConfig], Any],
    max_workers: int = 5,
) -> AggregatedResult:
    """Execute an action across target accounts in parallel with error isolation."""
    if not targets:
        return AggregatedResult(targets=[], results=[])

    if len(targets) == 1:
        email, config = targets[0]
        try:
            res_data = action(email, config)
            return AggregatedResult(targets, [AccountResult(email, success=True, data=res_data)])
        except Exception as e:
            return AggregatedResult(targets, [AccountResult(email, success=False, error=e)])

    # Multi-account parallel execution
    results: list[AccountResult] = []
    worker_count = min(len(targets), max_workers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_to_email = {pool.submit(action, email, cfg): email for email, cfg in targets}
        for future in concurrent.futures.as_completed(future_to_email):
            email = future_to_email[future]
            try:
                data = future.result()
                results.append(AccountResult(email, success=True, data=data))
            except Exception as e:
                results.append(AccountResult(email, success=False, error=e))

    # Maintain deterministic ordering matching input targets
    results_by_email = {r.email: r for r in results}
    ordered_results = [
        results_by_email.get(
            email,
            AccountResult(email, success=False, error=RuntimeError("Missing result")),
        )
        for email, _ in targets
    ]

    return AggregatedResult(targets, ordered_results)
