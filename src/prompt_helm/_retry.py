"""Retry primitives used by both the sync and async clients."""

from __future__ import annotations

import random as _random
import time
from collections.abc import Awaitable
from typing import Callable, TypeVar

T = TypeVar("T")

DEFAULT_BASE_DELAY_MS = 250
DEFAULT_MAX_DELAY_MS = 8_000


def compute_backoff(
    attempt: int,
    base_delay_ms: int = DEFAULT_BASE_DELAY_MS,
    max_delay_ms: int = DEFAULT_MAX_DELAY_MS,
    rng: Callable[[], float] = _random.random,
) -> int:
    """Exponential backoff with up to 100 ms of additive jitter, capped at ``max_delay_ms``."""

    exponential = base_delay_ms * (2**attempt)
    jitter = int(rng() * 100)
    return int(min(exponential + jitter, max_delay_ms))


def with_retry_sync(
    fn: Callable[[], T],
    *,
    max_retries: int,
    is_retryable: Callable[[BaseException], bool],
    base_delay_ms: int = DEFAULT_BASE_DELAY_MS,
    max_delay_ms: int = DEFAULT_MAX_DELAY_MS,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = _random.random,
) -> T:
    """Invoke ``fn`` with bounded exponential backoff retries (synchronous)."""

    attempt = 0
    while True:
        try:
            return fn()
        except BaseException as err:  # noqa: BLE001 — re-raised below.
            if attempt >= max_retries or not is_retryable(err):
                raise
            delay_ms = compute_backoff(attempt, base_delay_ms, max_delay_ms, rng)
            sleep(delay_ms / 1000)
            attempt += 1


async def with_retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    is_retryable: Callable[[BaseException], bool],
    base_delay_ms: int = DEFAULT_BASE_DELAY_MS,
    max_delay_ms: int = DEFAULT_MAX_DELAY_MS,
    sleep: Callable[[float], Awaitable[None]],
    rng: Callable[[], float] = _random.random,
) -> T:
    """Invoke awaitable ``fn`` with bounded exponential backoff retries (async)."""

    attempt = 0
    while True:
        try:
            return await fn()
        except BaseException as err:  # noqa: BLE001 — re-raised below.
            if attempt >= max_retries or not is_retryable(err):
                raise
            delay_ms = compute_backoff(attempt, base_delay_ms, max_delay_ms, rng)
            await sleep(delay_ms / 1000)
            attempt += 1
