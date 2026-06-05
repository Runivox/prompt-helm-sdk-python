"""Shared client configuration, request shaping, and retry policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any
from urllib.parse import urlparse

import httpx

from .errors import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    PromptHelmError,
    RateLimitError,
)
from .errors import (
    TimeoutError as PromptHelmTimeoutError,
)

DEFAULT_BASE_URL = "https://api.prompthelm.app"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 2
API_KEY_LENGTH = 36
API_KEY_PREFIX = "phk_"
PACKAGE_NAME = "prompt-helm"


def _sdk_version() -> str:
    """Resolve the installed package version from metadata, with a safe fallback."""

    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:  # pragma: no cover - only when run from source tree
        return "0.0.0"


SDK_USER_AGENT = f"prompt-helm-sdk-python/{_sdk_version()}"


@dataclass(frozen=True)
class ClientConfig:
    """Validated, immutable configuration shared by sync and async clients."""

    api_key: str
    base_url: str
    timeout_seconds: float
    max_retries: int
    user_agent: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def execute_url(self) -> str:
        return f"{self.base_url}/api/v1/gateway/execute"

    @property
    def stream_url(self) -> str:
        return f"{self.base_url}/api/v1/gateway/stream"

    def headers(self, *, accept: str) -> dict[str, str]:
        out: dict[str, str] = {
            "content-type": "application/json",
            "accept": accept,
            "authorization": f"Bearer {self.api_key}",
            "user-agent": self.user_agent,
        }
        for key, value in self.extra_headers.items():
            out[key.lower()] = value
        return out


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_hex(value: str) -> bool:
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def build_config(
    *,
    api_key: str,
    base_url: str | None,
    timeout: float | None,
    max_retries: int | None,
    user_agent: str | None,
    headers: Mapping[str, str] | None,
) -> ClientConfig:
    """Validate inputs and construct an immutable :class:`ClientConfig`."""

    if not isinstance(api_key, str) or api_key == "":
        raise ValueError(
            "PromptHelm: `api_key` is required. Provide a PromptHelm API key starting with `phk_`.",
        )
    if (
        not api_key.startswith(API_KEY_PREFIX)
        or len(api_key) != API_KEY_LENGTH
        or not _is_hex(api_key[len(API_KEY_PREFIX) :])
    ):
        raise ValueError(
            "PromptHelm: `api_key` must start with `phk_` followed by 32 hex characters.",
        )

    resolved_base_url = base_url if base_url is not None else DEFAULT_BASE_URL
    if not _is_valid_http_url(resolved_base_url):
        raise ValueError(f"PromptHelm: `base_url` is not a valid URL: {resolved_base_url}")

    resolved_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS
    if not isinstance(resolved_timeout, (int, float)) or resolved_timeout <= 0:
        raise ValueError("PromptHelm: `timeout` must be a positive number of seconds.")

    resolved_max_retries = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
    if not isinstance(resolved_max_retries, int) or resolved_max_retries < 0:
        raise ValueError("PromptHelm: `max_retries` must be a non-negative integer.")

    resolved_user_agent = f"{user_agent} {SDK_USER_AGENT}" if user_agent else SDK_USER_AGENT

    return ClientConfig(
        api_key=api_key,
        base_url=resolved_base_url.rstrip("/"),
        timeout_seconds=float(resolved_timeout),
        max_retries=resolved_max_retries,
        user_agent=resolved_user_agent,
        extra_headers=dict(headers) if headers else {},
    )


def build_request_body(
    *,
    prompt_slug: str | None,
    prompt_id: str | None,
    variables: Mapping[str, str] | None,
    system: str | None,
    user: str | None,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
    stop_sequences: list[str] | None,
    environment: str | None,
    timeout_ms: int | None,
) -> dict[str, Any]:
    """Convert pythonic kwargs into the camelCase JSON body the gateway expects."""

    if prompt_slug is None and prompt_id is None and system is None and user is None:
        raise ValueError(
            "PromptHelm: provide at least one of `prompt_slug`, `prompt_id`, `system`, or `user`.",
        )

    body: dict[str, Any] = {}
    if prompt_slug is not None:
        body["promptSlug"] = prompt_slug
    if prompt_id is not None:
        body["promptId"] = prompt_id
    if variables is not None:
        body["variables"] = dict(variables)
    if system is not None:
        body["system"] = system
    if user is not None:
        body["user"] = user
    if model is not None:
        body["model"] = model
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["maxTokens"] = max_tokens
    if top_p is not None:
        body["topP"] = top_p
    if stop_sequences is not None:
        body["stopSequences"] = list(stop_sequences)
    if environment is not None:
        body["environment"] = environment
    if timeout_ms is not None:
        body["timeoutMs"] = timeout_ms
    return body


def is_retryable(err: BaseException) -> bool:
    """Apply the same retry policy as the Node SDK."""

    if isinstance(err, PromptHelmTimeoutError):
        return False
    if isinstance(
        err,
        (AuthenticationError, AuthorizationError, NotFoundError, RateLimitError),
    ):
        return False
    if isinstance(err, PromptHelmError):
        return 500 <= err.status_code <= 599
    if isinstance(err, httpx.TimeoutException):
        return False
    return bool(isinstance(err, httpx.HTTPError))


def safe_decode_json(response: httpx.Response) -> Any:
    """Read an httpx response body as JSON without raising on malformed bodies."""

    try:
        text = response.text
    except (UnicodeDecodeError, httpx.HTTPError):
        return None
    if not text:
        return None
    try:
        import json

        return json.loads(text)
    except ValueError:
        return None
