"""Tests for the synchronous PromptHelm client."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from prompt_helm import (
    ApiError,
    AuthenticationError,
    PromptHelm,
    RateLimitError,
)
from prompt_helm.errors import TimeoutError as PromptHelmTimeoutError


def _client(api_key: str, base_url: str, **overrides: Any) -> PromptHelm:
    overrides.setdefault("max_retries", 0)
    return PromptHelm(api_key=api_key, base_url=base_url, **overrides)


def test_constructor_rejects_missing_api_key(base_url: str) -> None:
    with pytest.raises(ValueError, match="api_key"):
        PromptHelm(api_key="", base_url=base_url)


def test_constructor_rejects_invalid_api_key_format(base_url: str) -> None:
    with pytest.raises(ValueError, match="phk_"):
        PromptHelm(api_key="not-a-valid-key", base_url=base_url)


def test_constructor_rejects_non_hex_api_key_suffix(base_url: str) -> None:
    bad_key = "phk_" + "z" * 32
    with pytest.raises(ValueError, match="phk_"):
        PromptHelm(api_key=bad_key, base_url=base_url)


def test_constructor_rejects_invalid_base_url(api_key: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        PromptHelm(api_key=api_key, base_url="not a url")


def test_constructor_rejects_non_positive_timeout(api_key: str, base_url: str) -> None:
    with pytest.raises(ValueError, match="timeout"):
        PromptHelm(api_key=api_key, base_url=base_url, timeout=0)


def test_constructor_rejects_negative_max_retries(api_key: str, base_url: str) -> None:
    with pytest.raises(ValueError, match="max_retries"):
        PromptHelm(api_key=api_key, base_url=base_url, max_retries=-1)


@respx.mock
def test_execute_sends_expected_request_and_returns_typed_response(
    api_key: str,
    base_url: str,
    execute_url: str,
    successful_response: dict[str, Any],
) -> None:
    route = respx.post(execute_url).mock(return_value=httpx.Response(200, json=successful_response))

    with _client(api_key, base_url, user_agent="my-app/1.2.3") as client:
        result = client.execute(
            prompt_slug="welcome",
            variables={"name": "World"},
            temperature=0.7,
            max_tokens=128,
        )

    assert result.id == "exec_123"
    assert result.output == "Hello, World!"
    assert result.total_tokens == 15
    assert result.cost == pytest.approx(0.000_12)

    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {api_key}"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["accept"] == "application/json"
    assert request.headers["user-agent"].startswith("my-app/1.2.3 ")
    assert "prompt-helm-sdk-python/" in request.headers["user-agent"]

    body = json.loads(request.content)
    assert body == {
        "promptSlug": "welcome",
        "variables": {"name": "World"},
        "temperature": 0.7,
        "maxTokens": 128,
    }


@respx.mock
def test_execute_raises_authentication_error_on_401(
    api_key: str, base_url: str, execute_url: str
) -> None:
    respx.post(execute_url).mock(
        return_value=httpx.Response(
            401,
            json={
                "statusCode": 401,
                "errorCode": "UNAUTHORIZED",
                "message": "Bad token",
                "timestamp": "2026-06-05T10:30:00.000Z",
                "requestId": "req-1",
            },
        )
    )
    with (
        _client(api_key, base_url, max_retries=3) as client,
        pytest.raises(AuthenticationError) as info,
    ):
        client.execute(prompt_slug="welcome")
    assert info.value.status_code == 401
    assert info.value.error_code == "UNAUTHORIZED"
    assert info.value.request_id == "req-1"


@respx.mock
def test_execute_raises_rate_limit_error_on_429_without_retry(
    api_key: str, base_url: str, execute_url: str
) -> None:
    route = respx.post(execute_url).mock(
        return_value=httpx.Response(
            429,
            json={"statusCode": 429, "errorCode": "TOO_MANY_REQUESTS", "message": "Slow down"},
        )
    )
    with _client(api_key, base_url, max_retries=3) as client, pytest.raises(RateLimitError):
        client.execute(prompt_slug="welcome")
    assert route.call_count == 1


@respx.mock
def test_execute_retries_on_500_then_raises_api_error(
    api_key: str, base_url: str, execute_url: str
) -> None:
    route = respx.post(execute_url).mock(
        return_value=httpx.Response(
            500,
            json={"statusCode": 500, "errorCode": "INTERNAL_ERROR", "message": "Boom"},
        )
    )
    with _client(api_key, base_url, max_retries=2) as client, pytest.raises(ApiError):
        client.execute(prompt_slug="welcome")
    assert route.call_count == 3  # 1 initial + 2 retries


@respx.mock
def test_execute_recovers_after_transient_5xx(
    api_key: str,
    base_url: str,
    execute_url: str,
    successful_response: dict[str, Any],
) -> None:
    route = respx.post(execute_url).mock(
        side_effect=[
            httpx.Response(
                503, json={"statusCode": 503, "errorCode": "INTERNAL_ERROR", "message": "down"}
            ),
            httpx.Response(200, json=successful_response),
        ]
    )
    with _client(api_key, base_url, max_retries=2) as client:
        result = client.execute(prompt_slug="welcome")
    assert result.id == "exec_123"
    assert route.call_count == 2


@respx.mock
def test_execute_translates_httpx_timeout(api_key: str, base_url: str, execute_url: str) -> None:
    respx.post(execute_url).mock(side_effect=httpx.ConnectTimeout("slow"))
    with (
        _client(api_key, base_url, max_retries=0, timeout=1.5) as client,
        pytest.raises(PromptHelmTimeoutError) as info,
    ):
        client.execute(prompt_slug="welcome")
    assert info.value.timeout_ms == 1500


@respx.mock
def test_stream_yields_parsed_events(api_key: str, base_url: str, stream_url: str) -> None:
    sse_body = (
        'data: {"type":"chunk","content":"Hello"}\n\n'
        'data: {"type":"chunk","content":", World!"}\n\n'
        'data: {"type":"done","inputTokens":10,"outputTokens":5,'
        '"totalTokens":15,"cost":0.0001,"model":"gpt-4o-mini","latencyMs":150}\n\n'
    )
    respx.post(stream_url).mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
    )

    with _client(api_key, base_url) as client:
        events = list(client.stream(prompt_slug="welcome"))

    assert [e.type for e in events] == ["chunk", "chunk", "done"]
    chunks = [e for e in events if e.type == "chunk"]
    assert "".join(c.content for c in chunks) == "Hello, World!"  # type: ignore[attr-defined]


@respx.mock
def test_stream_raises_api_error_for_error_frame(
    api_key: str, base_url: str, stream_url: str
) -> None:
    sse_body = (
        'data: {"type":"chunk","content":"partial"}\n\n'
        'data: {"type":"error","errorCode":"PROVIDER_DOWN",'
        '"message":"Upstream provider failed","requestId":"req-99"}\n\n'
    )
    respx.post(stream_url).mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
    )
    with _client(api_key, base_url) as client, pytest.raises(ApiError) as info:
        for _ in client.stream(prompt_slug="welcome"):
            pass
    assert info.value.error_code == "PROVIDER_DOWN"
    assert info.value.request_id == "req-99"


@respx.mock
def test_stream_raises_typed_error_on_http_status(
    api_key: str, base_url: str, stream_url: str
) -> None:
    respx.post(stream_url).mock(
        return_value=httpx.Response(
            401,
            json={"statusCode": 401, "errorCode": "UNAUTHORIZED", "message": "Bad token"},
        )
    )
    with _client(api_key, base_url) as client, pytest.raises(AuthenticationError):
        for _ in client.stream(prompt_slug="welcome"):
            pass
