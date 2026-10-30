"""Base Google API service builder and error interceptor."""

from __future__ import annotations

from typing import Any

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from gsuite_cli.auth.token_store import load_account_credentials
from gsuite_cli.config import AccountConfig
from gsuite_cli.exceptions import AuthError, ServiceError, TokenExpiredError

# Cache of initialized service resources per (account, service_name, version, auth_type, subject)
_SERVICE_CACHE: dict[tuple[str, str, str, str, str | None], Resource] = {}


def get_service_client(
    email: str,
    service_name: str,
    version: str,
    account_config: AccountConfig | None = None,
) -> Resource:
    """Build and return an authenticated Google API service client."""
    auth_type = account_config.auth_type if account_config else "oauth"
    subject = account_config.resolved_subject(email) if account_config else None
    cache_key = (email, service_name, version, auth_type, subject)
    if cache_key in _SERVICE_CACHE:
        return _SERVICE_CACHE[cache_key]

    is_sa = bool(account_config and account_config.auth_type == "service_account")
    auto_refresh = not is_sa

    try:
        credentials = load_account_credentials(
            email,
            account_config=account_config,
            auto_refresh=auto_refresh,
        )
    except (TokenExpiredError, AuthError):
        raise
    except Exception as e:
        raise TokenExpiredError(
            f"Failed to load credentials for {email}: {e}. Run 'gsuite auth add {email}'.",
            account=email,
        )

    try:
        # cache_discovery=False prevents file-based discovery cache warnings
        service = build(
            service_name,
            version,
            credentials=credentials,
            cache_discovery=False,
        )
        _SERVICE_CACHE[cache_key] = service
        return service
    except Exception as e:
        raise ServiceError(
            f"Failed to build {service_name} {version} client for {email}: {e}",
            service=service_name,
            account=email,
        )


def execute_api_call(call_callable: Any, service_name: str, email: str) -> Any:
    """Execute a Google API request with robust error translation."""
    try:
        return call_callable.execute()
    except HttpError as e:
        status_code = e.resp.status if hasattr(e, "resp") else None
        reason = getattr(e, "reason", str(e))
        if status_code in (401, 403) and "invalid_grant" in str(e).lower():
            raise TokenExpiredError(
                f"Authentication expired or revoked for {email}. Run 'gsuite auth add {email}'.",
                account=email,
            )
        if (
            status_code == 400
            and "precondition check failed" in str(e).lower()
            and service_name.lower() == "gmail"
        ):
            raise ServiceError(
                f"Google {service_name} API HTTP 400 Precondition check failed for {email}. "
                "Gmail API requires Domain-Wide Delegation (impersonating a Google Workspace user subject) when using a service account.",
                service=service_name,
                account=email,
                status_code=400,
                details={"content": str(e.content) if hasattr(e, "content") else str(e)},
            )
        raise ServiceError(
            f"Google {service_name} API HTTP {status_code} error: {reason}",
            service=service_name,
            account=email,
            status_code=status_code,
            details={"content": str(e.content) if hasattr(e, "content") else str(e)},
        )
    except RefreshError as e:
        if "unauthorized_client" in str(e).lower():
            raise AuthError(
                f"Domain-Wide Delegation authorization is missing in Google Workspace Admin Console for {email}: {e}",
                account=email,
            )
        raise TokenExpiredError(
            f"Refresh token expired or revoked for {email}: {e}. Run 'gsuite auth add {email}'.",
            account=email,
        )
    except TimeoutError as e:
        raise ServiceError(
            f"Network timeout contacting Google {service_name} API: {e}",
            service=service_name,
            account=email,
            status_code=408,
        )
    except Exception as e:
        raise ServiceError(
            f"Google {service_name} API call failed: {e}",
            service=service_name,
            account=email,
        )
