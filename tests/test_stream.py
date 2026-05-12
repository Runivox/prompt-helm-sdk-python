"""Tests for the SSE parser and stream event decoder."""

from __future__ import annotations

import json

from prompt_helm._stream import SseParser, parse_stream_event
from prompt_helm.types import StreamChunkEvent, StreamDoneEvent, StreamErrorEvent


def test_parser_emits_single_frame_after_blank_line() -> None:
    parser = SseParser()
    frames = parser.feed("data: hello\n\n")
    assert [f.data for f in frames] == ["hello"]


def test_parser_handles_multi_line_data_field() -> None:
    parser = SseParser()
    frames = parser.feed("data: line1\ndata: line2\n\n")
    assert [f.data for f in frames] == ["line1\nline2"]


def test_parser_ignores_comments_and_unknown_fields() -> None:
    parser = SseParser()
    frames = parser.feed(": this is a comment\nevent: chunk\ndata: payload\n\n")
    assert [f.data for f in frames] == ["payload"]


def test_parser_buffers_across_chunks() -> None:
    parser = SseParser()
    assert parser.feed("data: par") == []
    assert parser.feed("tial\n") == []
    frames = parser.feed("\n")
    assert [f.data for f in frames] == ["partial"]


def test_parser_supports_crlf_line_endings() -> None:
    parser = SseParser()
    frames = parser.feed("data: ok\r\n\r\n")
    assert [f.data for f in frames] == ["ok"]


def test_parser_flush_emits_pending_data() -> None:
    parser = SseParser()
    parser.feed("data: tail\n")
    flushed = parser.flush()
    assert [f.data for f in flushed] == ["tail"]


def test_parse_stream_event_chunk() -> None:
    event = parse_stream_event(json.dumps({"type": "chunk", "content": "Hi"}))
    assert isinstance(event, StreamChunkEvent)
    assert event.content == "Hi"


def test_parse_stream_event_done() -> None:
    event = parse_stream_event(
        json.dumps(
            {
                "type": "done",
                "inputTokens": 10,
                "outputTokens": 4,
                "totalTokens": 14,
                "cost": 0.0001,
                "model": "gpt-4o-mini",
                "latencyMs": 250,
            }
        )
    )
    assert isinstance(event, StreamDoneEvent)
    assert event.total_tokens == 14
    assert event.latency_ms == 250


def test_parse_stream_event_error() -> None:
    event = parse_stream_event(
        json.dumps(
            {
                "type": "error",
                "errorCode": "PROVIDER_DOWN",
                "message": "Upstream is unavailable",
                "requestId": "req-1",
            }
        )
    )
    assert isinstance(event, StreamErrorEvent)
    assert event.error_code == "PROVIDER_DOWN"
    assert event.request_id == "req-1"


def test_parse_stream_event_returns_none_for_done_marker() -> None:
    assert parse_stream_event("[DONE]") is None


def test_parse_stream_event_returns_none_for_invalid_json() -> None:
    assert parse_stream_event("{not json") is None


def test_parse_stream_event_returns_none_for_unknown_type() -> None:
    assert parse_stream_event(json.dumps({"type": "ping"})) is None
