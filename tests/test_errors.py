"""Tests for the error subclass hierarchy and envelope parsing."""

from __future__ import annotations

import pytest

from prompt_helm.errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    PromptHelmError,
    RateLimitError,
    parse_error_response,
)
from prompt_helm.errors import (
    TimeoutError as PromptHelmTimeoutError,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, ApiError),
        (502, ApiError),
        (418, ApiError),
    ],
)
def test_parse_error_response_maps_status_to_subclass(
    status: int, expected: type[PromptHelmError]
) -> None:
    err = parse_error_response(
        status,
        {
            "statusCode": status,
            "error": "Failure",
            "message": "Custom message",
            "code": "ERR_X",
            "correlationId": "corr-1",
        },
    )
    assert isinstance(err, expected)
    assert err.status_code == status
    assert err.code == "ERR_X"
    assert err.correlation_id == "corr-1"
    assert str(err) == "Custom message"


def test_parse_error_response_uses_fallback_message_when_envelope_invalid() -> None:
    err = parse_error_response(401, None)
    assert isinstance(err, AuthenticationError)
    assert "API key" in str(err)
    assert err.code is None
    assert err.correlation_id is None


def test_parse_error_response_falls_back_when_body_is_partial() -> None:
    err = parse_error_response(429, {"error": "RateLimited"})
    assert isinstance(err, RateLimitError)
    assert "Rate limit" in str(err)


def test_timeout_error_carries_timeout_ms() -> None:
    exc = PromptHelmTimeoutError(1500)
    assert exc.timeout_ms == 1500
    assert "1500" in str(exc)


def test_repr_includes_diagnostic_fields() -> None:
    err = ApiError(500, "INTERNAL", "abc", "boom")
    rendered = repr(err)
    assert "ApiError" in rendered
    assert "500" in rendered
    assert "INTERNAL" in rendered
    assert "abc" in rendered
