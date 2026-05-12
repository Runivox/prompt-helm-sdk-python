"""Server-Sent Events parser for the PromptHelm gateway stream endpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .types import StreamChunkEvent, StreamDoneEvent, StreamErrorEvent, StreamEvent


@dataclass
class _Frame:
    data: str


class SseParser:
    """Buffered SSE frame extractor.

    Feeds raw text chunks and yields completed ``data`` frames once a blank
    line terminator has been observed. Comment lines (starting with ``:``) and
    non-``data`` fields are ignored, matching the Node SDK behaviour.
    """

    def __init__(self) -> None:
        self._buffer: str = ""
        self._data_lines: list[str] = []

    def feed(self, chunk: str) -> list[_Frame]:
        self._buffer += chunk
        frames: list[_Frame] = []

        while True:
            idx, length = self._index_of_line_end(self._buffer)
            if idx == -1:
                break
            line = self._buffer[:idx]
            self._buffer = self._buffer[idx + length :]

            if line == "":
                if self._data_lines:
                    frames.append(_Frame(data="\n".join(self._data_lines)))
                    self._data_lines = []
                continue

            if line.startswith(":"):
                continue

            colon = line.find(":")
            if colon == -1:
                field, value = line, ""
            else:
                field = line[:colon]
                value = line[colon + 1 :]
                if value.startswith(" "):
                    value = value[1:]

            if field == "data":
                self._data_lines.append(value)

        return frames

    def flush(self) -> list[_Frame]:
        if not self._data_lines:
            return []
        frame = _Frame(data="\n".join(self._data_lines))
        self._data_lines = []
        return [frame]

    @staticmethod
    def _index_of_line_end(buf: str) -> tuple[int, int]:
        crlf = buf.find("\r\n")
        lf = buf.find("\n")
        cr = buf.find("\r")

        if crlf != -1 and (lf == -1 or crlf <= lf) and (cr == -1 or crlf <= cr):
            return crlf, 2
        if lf != -1 and (cr == -1 or lf < cr):
            return lf, 1
        if cr != -1:
            return cr, 1
        return -1, 0


def parse_stream_event(data: str) -> StreamEvent | None:
    """Decode an SSE ``data`` payload into a typed stream event, or ``None`` to skip."""

    trimmed = data.strip()
    if trimmed == "" or trimmed == "[DONE]":
        return None
    try:
        parsed: Any = json.loads(trimmed)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None

    event_type = parsed.get("type")
    if event_type == "chunk":
        content = parsed.get("content")
        if isinstance(content, str):
            return StreamChunkEvent(content=content)
        return None
    if event_type == "done":
        try:
            return StreamDoneEvent(
                input_tokens=int(parsed["inputTokens"]),
                output_tokens=int(parsed["outputTokens"]),
                total_tokens=int(parsed["totalTokens"]),
                cost=float(parsed["cost"]),
                model=str(parsed["model"]),
                latency_ms=int(parsed["latencyMs"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if event_type == "error":
        error_code = parsed.get("errorCode")
        message = parsed.get("message")
        if isinstance(error_code, str) and isinstance(message, str):
            request_id = parsed.get("requestId")
            return StreamErrorEvent(
                error_code=error_code,
                message=message,
                request_id=request_id if isinstance(request_id, str) else None,
            )
    return None
