"""Official Python SDK for PromptHelm.

>>> from prompt_helm import PromptHelm
>>> ph = PromptHelm(api_key="phk_<your-32-hex-token>")
>>> result = ph.execute(prompt_slug="welcome", variables={"name": "World"})
>>> print(result.output)
"""

from __future__ import annotations

from ._client_async import AsyncPromptHelm
from ._client_sync import PromptHelm
from .errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    PromptHelmError,
    RateLimitError,
    TimeoutError,
    parse_error_response,
)
from .types import (
    Environment,
    ErrorEnvelope,
    ExecuteResponse,
    StreamChunkEvent,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamEvent,
)

__version__ = "0.1.0"

__all__ = [
    "ApiError",
    "AsyncPromptHelm",
    "AuthenticationError",
    "AuthorizationError",
    "Environment",
    "ErrorEnvelope",
    "ExecuteResponse",
    "NotFoundError",
    "PromptHelm",
    "PromptHelmError",
    "RateLimitError",
    "StreamChunkEvent",
    "StreamDoneEvent",
    "StreamErrorEvent",
    "StreamEvent",
    "TimeoutError",
    "__version__",
    "parse_error_response",
]
