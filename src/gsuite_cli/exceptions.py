"""Custom exception hierarchy for gsuite-cli."""


class GSuiteError(Exception):
    """Base exception for all gsuite-cli errors."""

    def __init__(self, message: str, code: str = "GENERAL_ERROR", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(GSuiteError):
    """Raised when configuration file is invalid or missing."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


class AuthError(GSuiteError):
    """Raised when authentication or token retrieval/refresh fails."""

    def __init__(self, message: str, account: str | None = None, details: dict | None = None):
        details = details or {}
        if account:
            details["account"] = account
        super().__init__(message, code="AUTH_ERROR", details=details)
        self.account = account


class TokenExpiredError(AuthError):
    """Raised when a token is expired and refresh token is missing or revoked."""

    def __init__(self, message: str, account: str | None = None):
        super().__init__(message, account=account, details={"expired": True})
        self.code = "TOKEN_EXPIRED"


class TargetingError(GSuiteError):
    """Raised when account or label targeting fails or matches no accounts."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="TARGETING_ERROR", details=details)


class ServiceError(GSuiteError):
    """Raised when a Google API call fails."""

    def __init__(
        self,
        message: str,
        service: str | None = None,
        account: str | None = None,
        status_code: int | None = None,
        details: dict | None = None,
    ):
        details = details or {}
        if service:
            details["service"] = service
        if account:
            details["account"] = account
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, code="SERVICE_ERROR", details=details)
