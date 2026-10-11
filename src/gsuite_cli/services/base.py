"""Base Google API service builder and error interceptor."""

from __future__ import annotations

from typing import Any

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from gsuite_cli.auth.token_store import load_credentials
from gsuite_cli.config import AccountConfig
from gsuite_cli.exceptions import ServiceError, TokenExpiredError

# Cache of initialized service resources per (account, service_name, version)
_SERVICE_CACHE: dict[tuple[str, str, str], Resource] = {}


def get_service_client(
    email: str,
    service_name: str,
    version: str,
    account_config: AccountConfig | None = None,
) -> Resource:
    """Build and return an authenticated Google API service client."""
    cache_key = (email, service_name, version)
    if cache_key in _SERVICE_CACHE:
        return _SERVICE_CACHE[cache_key]

    token_path = account_config.token_file if account_config else None

    try:
        credentials = load_credentials(email, custom_path=token_path, auto_refresh=True)
    except TokenExpiredError:
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
        raise ServiceError(
            f"Google {service_name} API HTTP {status_code} error: {reason}",
            service=service_name,
            account=email,
            status_code=status_code,
            details={"content": str(e.content) if hasattr(e, "content") else str(e)},
        )
    except RefreshError as e:
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
