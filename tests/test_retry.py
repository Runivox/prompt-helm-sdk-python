"""Tests for the retry primitives."""

from __future__ import annotations

import pytest

from prompt_helm._retry import compute_backoff, with_retry_async, with_retry_sync


def test_compute_backoff_uses_exponential_growth() -> None:
    delays = [compute_backoff(i, 100, 10_000, rng=lambda: 0.0) for i in range(4)]
    assert delays == [100, 200, 400, 800]


def test_compute_backoff_caps_at_max_delay() -> None:
    delay = compute_backoff(20, 100, 1_000, rng=lambda: 0.0)
    assert delay == 1_000


def test_compute_backoff_adds_jitter() -> None:
    delay = compute_backoff(0, 100, 10_000, rng=lambda: 0.99)
    assert 100 < delay <= 200


def test_with_retry_sync_returns_immediately_on_success() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        return "ok"

    out = with_retry_sync(fn, max_retries=3, is_retryable=lambda _e: True, sleep=lambda _s: None)
    assert out == "ok"
    assert calls["n"] == 1


def test_with_retry_sync_retries_until_success() -> None:
    attempts = {"n": 0}

    def fn() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return "done"

    out = with_retry_sync(
        fn,
        max_retries=5,
        is_retryable=lambda _e: True,
        sleep=lambda _s: None,
        rng=lambda: 0.0,
    )
    assert out == "done"
    assert attempts["n"] == 3


def test_with_retry_sync_raises_after_max_retries() -> None:
    attempts = {"n": 0}

    def fn() -> None:
        attempts["n"] += 1
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        with_retry_sync(
            fn,
            max_retries=2,
            is_retryable=lambda _e: True,
            sleep=lambda _s: None,
            rng=lambda: 0.0,
        )
    assert attempts["n"] == 3  # initial + 2 retries


def test_with_retry_sync_does_not_retry_when_predicate_returns_false() -> None:
    attempts = {"n": 0}

    def fn() -> None:
        attempts["n"] += 1
        raise ValueError("bad")

    with pytest.raises(ValueError):
        with_retry_sync(
            fn,
            max_retries=5,
            is_retryable=lambda _e: False,
            sleep=lambda _s: None,
        )
    assert attempts["n"] == 1


async def test_with_retry_async_retries_until_success() -> None:
    attempts = {"n": 0}

    async def fn() -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    async def fake_sleep(_seconds: float) -> None:
        return None

    out = await with_retry_async(
        fn,
        max_retries=3,
        is_retryable=lambda _e: True,
        sleep=fake_sleep,
        rng=lambda: 0.0,
    )
    assert out == "ok"
    assert attempts["n"] == 2
