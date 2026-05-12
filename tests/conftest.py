"""Shared pytest fixtures for the PromptHelm SDK test suite."""

from __future__ import annotations

import pytest

VALID_API_KEY = "phk_" + ("a" * 32)
TEST_BASE_URL = "https://api.prompthelm.test"


@pytest.fixture
def api_key() -> str:
    return VALID_API_KEY


@pytest.fixture
def base_url() -> str:
    return TEST_BASE_URL


@pytest.fixture
def execute_url(base_url: str) -> str:
    return f"{base_url}/api/v1/gateway/execute"


@pytest.fixture
def stream_url(base_url: str) -> str:
    return f"{base_url}/api/v1/gateway/stream"


@pytest.fixture
def successful_response() -> dict[str, object]:
    return {
        "id": "exec_123",
        "output": "Hello, World!",
        "model": "gpt-4o-mini",
        "inputTokens": 10,
        "outputTokens": 5,
        "totalTokens": 15,
        "latencyMs": 220,
        "cost": 0.000_12,
        "timestamp": "2026-05-13T10:00:00.000Z",
    }
