"""Typed error hierarchy for the PromptHelm SDK."""

from __future__ import annotations

from typing import Any


class PromptHelmError(Exception):
    """Base class for all PromptHelm API errors.

    Mirrors the server error envelope. Every instance surfaces
    ``status_code``, ``error_code``, ``message`` (via ``str(err)``) and
    ``request_id`` for end-to-end traceability against PromptHelm logs.
    """

    def __init__(
        self,
        status_code: int,
        error_code: str | None,
        request_id: str | None,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id

    @property
    def message(self) -> str:
        """The human-readable error message (same as ``str(self)``)."""

        return str(self)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status_code={self.status_code!r}, "
            f"error_code={self.error_code!r}, request_id={self.request_id!r}, "
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
    """Detect the server envelope ``{statusCode, errorCode, message, ...}``.

    ``message`` may be a string or an array of strings (validation errors).
    Only ``statusCode`` and ``errorCode`` are required to recognise the shape.
    """

    if not isinstance(value, dict):
        return False
    return isinstance(value.get("statusCode"), int) and isinstance(value.get("errorCode"), str)


def _coerce_message(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "; ".join(value) if value else fallback
    return fallback


def parse_error_response(status: int, body: Any) -> PromptHelmError:
    """Map an HTTP status + decoded body to the most specific error subclass.

    Reads the PromptHelm JSON error envelope:
    ``{ statusCode, errorCode, message, timestamp, requestId }``.
    """

    envelope = body if _is_error_envelope(body) else None
    fallback = _fallback_message(status)
    message = _coerce_message(envelope.get("message"), fallback) if envelope else fallback
    error_code = envelope.get("errorCode") if envelope else None
    request_id = envelope.get("requestId") if envelope else None
    if not isinstance(request_id, str):
        request_id = None

    if status == 401:
        return AuthenticationError(status, error_code, request_id, message)
    if status == 403:
        return AuthorizationError(status, error_code, request_id, message)
    if status == 404:
        return NotFoundError(status, error_code, request_id, message)
    if status == 429:
        return RateLimitError(status, error_code, request_id, message)
    return ApiError(status, error_code, request_id, message)
