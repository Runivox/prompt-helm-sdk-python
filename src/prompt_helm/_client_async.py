"""Asynchronous PromptHelm client implementation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from types import TracebackType
from typing import Any

import httpx

from ._client import (
    ClientConfig,
    build_config,
    build_request_body,
    is_retryable,
    safe_decode_json,
)
from ._retry import with_retry_async
from ._stream import SseParser, parse_stream_event
from .errors import (
    ApiError,
    parse_error_response,
)
from .errors import (
    TimeoutError as PromptHelmTimeoutError,
)
from .types import ExecuteResponse, StreamErrorEvent, StreamEvent


class AsyncPromptHelm:
    """Asynchronous HTTP client for the PromptHelm gateway."""

    _config: ClientConfig
    _client: httpx.AsyncClient
    _owns_client: bool

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        user_agent: str | None = None,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = build_config(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent,
            headers=headers,
        )
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=self._config.timeout_seconds)
            self._owns_client = True

    async def __aenter__(self) -> AsyncPromptHelm:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        *,
        prompt_slug: str | None = None,
        prompt_id: str | None = None,
        variables: Mapping[str, str] | None = None,
        system: str | None = None,
        user: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        environment: str | None = None,
        timeout_ms: int | None = None,
    ) -> ExecuteResponse:
        """Execute a managed prompt and return the full response."""

        body = build_request_body(
            prompt_slug=prompt_slug,
            prompt_id=prompt_id,
            variables=variables,
            system=system,
            user=user,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop_sequences=stop_sequences,
            environment=environment,
            timeout_ms=timeout_ms,
        )

        return await with_retry_async(
            lambda: self._execute_once(body),
            max_retries=self._config.max_retries,
            is_retryable=is_retryable,
            sleep=asyncio.sleep,
        )

    def stream(
        self,
        *,
        prompt_slug: str | None = None,
        prompt_id: str | None = None,
        variables: Mapping[str, str] | None = None,
        system: str | None = None,
        user: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        environment: str | None = None,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Execute a managed prompt and yield streamed events as they arrive."""

        body = build_request_body(
            prompt_slug=prompt_slug,
            prompt_id=prompt_id,
            variables=variables,
            system=system,
            user=user,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop_sequences=stop_sequences,
            environment=environment,
            timeout_ms=timeout_ms,
        )
        return self._stream(body)

    async def _execute_once(self, body: dict[str, Any]) -> ExecuteResponse:
        try:
            response = await self._client.post(
                self._config.execute_url,
                json=body,
                headers=self._config.headers(accept="application/json"),
                timeout=self._config.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise PromptHelmTimeoutError(int(self._config.timeout_seconds * 1000)) from exc

        if response.status_code >= 400:
            error_body = safe_decode_json(response)
            raise parse_error_response(response.status_code, error_body)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError(
                response.status_code,
                None,
                None,
                "Server returned a malformed JSON response.",
            ) from exc

        if not isinstance(payload, dict):
            raise ApiError(
                response.status_code,
                None,
                None,
                "Server returned an unexpected response shape.",
            )

        return ExecuteResponse(
            id=str(payload["id"]),
            output=str(payload["output"]),
            model=str(payload["model"]),
            input_tokens=int(payload["inputTokens"]),
            output_tokens=int(payload["outputTokens"]),
            total_tokens=int(payload["totalTokens"]),
            latency_ms=int(payload["latencyMs"]),
            cost=float(payload["cost"]),
            timestamp=str(payload["timestamp"]),
        )

    async def _stream(self, body: dict[str, Any]) -> AsyncIterator[StreamEvent]:
        headers = self._config.headers(accept="text/event-stream")
        try:
            async with self._client.stream(
                "POST",
                self._config.stream_url,
                json=body,
                headers=headers,
                timeout=self._config.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    error_body = safe_decode_json(response)
                    raise parse_error_response(response.status_code, error_body)

                parser = SseParser()
                async for chunk in response.aiter_text():
                    if not chunk:
                        continue
                    for frame in parser.feed(chunk):
                        event = parse_stream_event(frame.data)
                        if event is None:
                            continue
                        if isinstance(event, StreamErrorEvent):
                            raise ApiError(
                                500,
                                event.error_code,
                                event.request_id,
                                event.message,
                            )
                        yield event
                for frame in parser.flush():
                    event = parse_stream_event(frame.data)
                    if event is None:
                        continue
                    if isinstance(event, StreamErrorEvent):
                        raise ApiError(500, event.error_code, event.request_id, event.message)
                    yield event
        except httpx.TimeoutException as exc:
            raise PromptHelmTimeoutError(int(self._config.timeout_seconds * 1000)) from exc
