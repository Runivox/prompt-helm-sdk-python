"""Tests for the asynchronous PromptHelm client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from prompt_helm import (
    ApiError,
    AsyncPromptHelm,
    AuthenticationError,
    RateLimitError,
)
from prompt_helm.errors import TimeoutError as PromptHelmTimeoutError


def _client(api_key: str, base_url: str, **overrides: Any) -> AsyncPromptHelm:
    overrides.setdefault("max_retries", 0)
    return AsyncPromptHelm(api_key=api_key, base_url=base_url, **overrides)


@respx.mock
async def test_async_execute_returns_typed_response(
    api_key: str,
    base_url: str,
    execute_url: str,
    successful_response: dict[str, Any],
) -> None:
    respx.post(execute_url).mock(return_value=httpx.Response(200, json=successful_response))
    async with _client(api_key, base_url) as client:
        result = await client.execute(prompt_slug="welcome")
    assert result.output == "Hello, World!"
    assert result.input_tokens == 10


@respx.mock
async def test_async_execute_raises_authentication_error(
    api_key: str, base_url: str, execute_url: str
) -> None:
    respx.post(execute_url).mock(
        return_value=httpx.Response(
            401, json={"statusCode": 401, "errorCode": "UNAUTHORIZED", "message": "bad"}
        )
    )
    async with _client(api_key, base_url, max_retries=3) as client:
        with pytest.raises(AuthenticationError):
            await client.execute(prompt_slug="welcome")


@respx.mock
async def test_async_execute_does_not_retry_on_429(
    api_key: str, base_url: str, execute_url: str
) -> None:
    route = respx.post(execute_url).mock(
        return_value=httpx.Response(
            429, json={"statusCode": 429, "errorCode": "TOO_MANY_REQUESTS", "message": "limited"}
        )
    )
    async with _client(api_key, base_url, max_retries=3) as client:
        with pytest.raises(RateLimitError):
            await client.execute(prompt_slug="welcome")
    assert route.call_count == 1


@respx.mock
async def test_async_execute_retries_5xx_then_raises(
    api_key: str, base_url: str, execute_url: str
) -> None:
    route = respx.post(execute_url).mock(
        return_value=httpx.Response(
            502, json={"statusCode": 502, "errorCode": "INTERNAL_ERROR", "message": "bad"}
        )
    )
    async with _client(api_key, base_url, max_retries=2) as client:
        with pytest.raises(ApiError):
            await client.execute(prompt_slug="welcome")
    assert route.call_count == 3


@respx.mock
async def test_async_execute_translates_timeout(
    api_key: str, base_url: str, execute_url: str
) -> None:
    respx.post(execute_url).mock(side_effect=httpx.ReadTimeout("slow"))
    async with _client(api_key, base_url, timeout=2.0) as client:
        with pytest.raises(PromptHelmTimeoutError) as info:
            await client.execute(prompt_slug="welcome")
    assert info.value.timeout_ms == 2000


@respx.mock
async def test_async_stream_yields_events(api_key: str, base_url: str, stream_url: str) -> None:
    sse_body = (
        'data: {"type":"chunk","content":"hi"}\n\n'
        'data: {"type":"done","inputTokens":1,"outputTokens":2,"totalTokens":3,'
        '"cost":0.0,"model":"m","latencyMs":10}\n\n'
    )
    respx.post(stream_url).mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
    )
    async with _client(api_key, base_url) as client:
        events = [event async for event in client.stream(prompt_slug="welcome")]
    assert [e.type for e in events] == ["chunk", "done"]


@respx.mock
async def test_async_stream_raises_on_error_frame(
    api_key: str, base_url: str, stream_url: str
) -> None:
    sse_body = (
        'data: {"type":"error","errorCode":"PROVIDER_DOWN",'
        '"message":"down","requestId":"req-7"}\n\n'
    )
    respx.post(stream_url).mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
    )
    async with _client(api_key, base_url) as client:
        with pytest.raises(ApiError) as info:
            async for _ in client.stream(prompt_slug="welcome"):
                pass
    assert info.value.error_code == "PROVIDER_DOWN"
    assert info.value.request_id == "req-7"


async def test_async_constructor_validates_api_key(base_url: str) -> None:
    with pytest.raises(ValueError, match="api_key"):
        AsyncPromptHelm(api_key="", base_url=base_url)
