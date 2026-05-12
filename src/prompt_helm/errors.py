"""Typed error hierarchy for the PromptHelm SDK."""

from __future__ import annotations

from typing import Any


class PromptHelmError(Exception):
    """Base class for all PromptHelm API errors."""

    def __init__(
        self,
        status_code: int,
        code: str | None,
        correlation_id: str | None,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.correlation_id = correlation_id

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status_code={self.status_code!r}, "
            f"code={self.code!r}, correlation_id={self.correlation_id!r}, "
            f"message={str(self)!r})"
        )


class AuthenticationError(PromptHelmError):
    """Raised on HTTP 401 — the API key is missing, invalid, or revoked."""


class AuthorizationError(PromptHelmError):
    """Raised on HTTP 403 — the caller is authenticated but lacks permission."""


class NotFoundError(PromptHelmError):
    """Raised on HTTP 404 — the prompt or resource does not exist."""


class RateLimitError(PromptHelmError):
    """Raised on HTTP 429 — request rate exceeded the configured quota."""


class ApiError(PromptHelmError):
    """Raised on HTTP 5xx and any unexpected non-success response."""


class TimeoutError(Exception):  # noqa: A001 — public API mirrors Node SDK.
    """Raised when an HTTP request exceeds the configured client timeout."""

    def __init__(self, timeout_ms: int, message: str | None = None) -> None:
        super().__init__(message or f"Request timed out after {timeout_ms}ms")
        self.timeout_ms = timeout_ms


def _fallback_message(status: int) -> str:
    if status == 401:
        return "Authentication failed. Check that your API key is valid and not revoked."
    if status == 403:
        return "You do not have permission to perform this action."
    if status == 404:
        return "The requested prompt or resource was not found."
    if status == 429:
        return "Rate limit exceeded. Slow down requests or upgrade your plan."
    if status >= 500:
        return "PromptHelm encountered an internal error. The request can be retried."
    return f"Request failed with status {status}."


def _is_error_envelope(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        isinstance(value.get("statusCode"), int)
        and isinstance(value.get("error"), str)
        and isinstance(value.get("message"), str)
    )


def parse_error_response(status: int, body: Any) -> PromptHelmError:
    """Map an HTTP status + decoded body to the most specific error subclass."""

    envelope = body if _is_error_envelope(body) else None
    message = envelope["message"] if envelope else _fallback_message(status)
    code = envelope.get("code") if envelope else None
    correlation_id = envelope.get("correlationId") if envelope else None

    if status == 401:
        return AuthenticationError(status, code, correlation_id, message)
    if status == 403:
        return AuthorizationError(status, code, correlation_id, message)
    if status == 404:
        return NotFoundError(status, code, correlation_id, message)
    if status == 429:
        return RateLimitError(status, code, correlation_id, message)
    return ApiError(status, code, correlation_id, message)
