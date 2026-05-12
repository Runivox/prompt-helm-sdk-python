"""Public dataclasses and typed dictionaries for the PromptHelm SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

Environment = Literal["production", "development"]


@dataclass(frozen=True)
class ExecuteResponse:
    """Result of a non-streaming gateway execution."""

    id: str
    output: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    cost: float
    timestamp: str


@dataclass(frozen=True)
class StreamChunkEvent:
    """A partial token chunk emitted while the model is generating."""

    content: str
    type: Literal["chunk"] = "chunk"


@dataclass(frozen=True)
class StreamDoneEvent:
    """Final usage / cost frame emitted when generation completes."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    model: str
    latency_ms: int
    type: Literal["done"] = "done"


@dataclass(frozen=True)
class StreamErrorEvent:
    """Terminal error frame emitted by the gateway mid-stream."""

    error_code: str
    message: str
    request_id: str | None = None
    type: Literal["error"] = "error"


StreamEvent = Union[StreamChunkEvent, StreamDoneEvent, StreamErrorEvent]


@dataclass(frozen=True)
class ErrorEnvelope:
    """The error shape returned by the PromptHelm API."""

    status_code: int
    error: str
    message: str
    code: str | None = None
    correlation_id: str | None = None
