"""Provider adapter tests — httpx.MockTransport, zero network.

The A-1b deliverable: a TRANSCRIPT proving tool-call normalization works for
both formats, and that weird finish/stop reasons map to typed errors
(GUIA A3 test requirement).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from tlamati.core.messages import (
    Message,
    MessageEnd,
    TextDelta,
    ToolCall,
    ToolCallArgsDelta,
    ToolCallStart,
    ToolResult,
    Usage,
)
from tlamati.providers.anthropic_messages import AnthropicMessages
from tlamati.providers.base import ProviderError, ToolSpec
from tlamati.providers.openai_compat import OpenAICompat

# --------------------------------------------------------------------------
# Helpers: canned SSE streams
# --------------------------------------------------------------------------


def sse_response(chunks: list[dict[str, Any] | str]) -> httpx.Response:
    """Build an SSE response body from dicts (auto-serialized) or raw strings."""
    lines = []
    for c in chunks:
        payload = c if isinstance(c, str) else json.dumps(c)
        lines.append(f"data: {payload}\n\n")
    lines.append("data: [DONE]\n\n")
    return httpx.Response(
        200,
        content="".join(lines).encode(),
        headers={"content-type": "text/event-stream"},
    )


def capture_request() -> tuple[dict[str, Any], httpx.MockTransport]:
    """MockTransport that records the outgoing request body."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return seen.get("response", sse_response([]))

    return seen, httpx.MockTransport(handler)


def set_response(seen: dict[str, Any], response: httpx.Response) -> None:
    seen["response"] = response


async def collect(provider: Any, messages: list[Message], tools: list[ToolSpec]) -> list[Any]:
    return [ev async for ev in provider.stream(messages, tools)]


TOOL = ToolSpec(
    name="read_file",
    description="Read a file",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
)


# --------------------------------------------------------------------------
# OpenAICompat
# --------------------------------------------------------------------------


class TestOpenAICompat:
    async def test_text_stream_transcript(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {"choices": [{"delta": {"content": "Hola "}, "finish_reason": None}]},
                    {"choices": [{"delta": {"content": "mundo"}, "finish_reason": None}]},
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                    {"usage": {"prompt_tokens": 11, "completion_tokens": 2}},
                ]
            ),
        )
        p = OpenAICompat(model="m", base_url="https://x/api", api_key="***", transport=transport)
        events = await collect(p, [Message(role="user", content="hi")], [])

        texts = [e.text for e in events if isinstance(e, TextDelta)]
        assert texts == ["Hola ", "mundo"]
        end = events[-1]
        assert isinstance(end, MessageEnd)
        assert end.stop_reason == "end_turn"
        assert end.usage.input_tokens == 11
        assert end.usage.output_tokens == 2
        # request shape
        assert seen["url"] == "https://x/api/chat/completions"
        assert seen["body"]["stream"] is True
        assert seen["headers"]["authorization"] == "Bearer ***"

    async def test_toolcall_normalization_transcript(self) -> None:
        """THE A-1b deliverable: fragmented tool args reassemble into one
        ToolCallStart + ordered ToolCallArgsDelta stream + stop=tool_use."""
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_1",
                                            "function": {
                                                "name": "read_file",
                                                "arguments": '{"pa',
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {"index": 0, "function": {"arguments": 'th": "a.py"}'}}
                                    ]
                                }
                            }
                        ]
                    },
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                ]
            ),
        )
        p = OpenAICompat(model="m", base_url="https://x/api", transport=transport)
        events = await collect(p, [Message(role="user", content="lee a.py")], [TOOL])

        starts = [e for e in events if isinstance(e, ToolCallStart)]
        assert len(starts) == 1
        assert (starts[0].id, starts[0].name) == ("call_1", "read_file")
        args = "".join(e.args_json for e in events if isinstance(e, ToolCallArgsDelta))
        assert json.loads(args) == {"path": "a.py"}
        end = events[-1]
        assert isinstance(end, MessageEnd) and end.stop_reason == "tool_use"
        # tools were converted to OpenAI shape
        fn = seen["body"]["tools"][0]["function"]
        assert fn["name"] == "read_file" and "parameters" in fn

    async def test_weird_finish_reason_maps_to_typed_error(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {"choices": [{"delta": {"content": "x"}, "finish_reason": "banana"}]},
                ]
            ),
        )
        p = OpenAICompat(model="m", base_url="https://x/api", transport=transport)
        events = await collect(p, [Message(role="user", content="hi")], [])
        end = events[-1]
        assert isinstance(end, MessageEnd)
        assert end.stop_reason == "error"
        assert "banana" in (end.error or "")

    async def test_broken_toolcall_json_maps_to_error_with_raw(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "c1",
                                            "function": {
                                                "name": "t",
                                                "arguments": "{not json",
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                ]
            ),
        )
        p = OpenAICompat(model="m", base_url="https://x/api", transport=transport)
        events = await collect(p, [Message(role="user", content="hi")], [TOOL])
        end = events[-1]
        assert isinstance(end, MessageEnd) and end.stop_reason == "error"
        assert "not json" in (end.error or "")

    async def test_content_filter_maps_to_refusal(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response([{"choices": [{"delta": {}, "finish_reason": "content_filter"}]}]),
        )
        p = OpenAICompat(model="m", base_url="https://x/api", transport=transport)
        end = (await collect(p, [Message(role="user", content="hi")], []))[-1]
        assert isinstance(end, MessageEnd) and end.stop_reason == "refusal"

    async def test_http_error_typed_retryable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="rate limited")

        p = OpenAICompat(
            model="m", base_url="https://x/api", transport=httpx.MockTransport(handler)
        )
        with pytest.raises(ProviderError) as ei:
            await collect(p, [Message(role="user", content="hi")], [])
        assert ei.value.retryable and ei.value.status == 429

    async def test_error_body_inside_200_stream(self) -> None:
        seen, transport = capture_request()
        set_response(seen, sse_response([{"error": {"message": "bad key"}}]))
        p = OpenAICompat(model="m", base_url="https://x/api", transport=transport)
        end = (await collect(p, [Message(role="user", content="hi")], []))[-1]
        assert isinstance(end, MessageEnd) and end.stop_reason == "error"
        assert "bad key" in (end.error or "")

    def test_message_conversion_all_roles(self) -> None:
        p = OpenAICompat(model="m")
        sys_m = p._convert_message(Message(role="system", content="s"))
        assert sys_m == {"role": "system", "content": "s"}
        tool_m = p._convert_message(
            Message(role="tool", tool_result=ToolResult(tool_call_id="c1", content="r"))
        )
        assert tool_m["tool_call_id"] == "c1"
        asst_m = p._convert_message(
            Message(
                role="assistant",
                tool_calls=(ToolCall(id="c1", name="t", arguments={"a": 1}),),
            )
        )
        assert asst_m["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'


# --------------------------------------------------------------------------
# AnthropicMessages
# --------------------------------------------------------------------------


def anthropic_tool_stream() -> httpx.Response:
    return sse_response(
        [
            {
                "type": "message_start",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "cache_read_input_tokens": 90,
                        "output_tokens": 1,
                    }
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "tu_1", "name": "read_file"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"path"'},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": ': "a.py"}'},
            },
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"output_tokens": 12},
            },
        ]
    )


class TestAnthropicMessages:
    async def test_toolcall_normalization_transcript(self) -> None:
        seen, transport = capture_request()
        set_response(seen, anthropic_tool_stream())
        p = AnthropicMessages(model="claude-x", api_key="***", transport=transport)
        events = await collect(
            p,
            [
                Message(role="system", content="eres tlamati"),
                Message(role="user", content="lee a.py"),
            ],
            [TOOL],
        )
        starts = [e for e in events if isinstance(e, ToolCallStart)]
        assert len(starts) == 1 and starts[0].id == "tu_1"
        assert starts[0].name == "read_file"
        args = "".join(e.args_json for e in events if isinstance(e, ToolCallArgsDelta))
        assert json.loads(args) == {"path": "a.py"}
        end = events[-1]
        assert isinstance(end, MessageEnd)
        assert end.stop_reason == "tool_use"
        # usage merged from message_start + message_delta, cache VISIBLE
        assert end.usage.input_tokens == 100
        assert end.usage.cache_read_tokens == 90
        assert end.usage.output_tokens == 12
        # request shape: headers + cache breakpoint on system and last tool
        assert seen["headers"]["x-api-key"] == "***"
        assert seen["headers"]["anthropic-version"] == "2023-06-01"
        assert seen["body"]["system"][-1]["cache_control"] == {"type": "ephemeral"}
        assert seen["body"]["tools"][-1]["cache_control"] == {"type": "ephemeral"}

    async def test_text_stream(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
                    {
                        "type": "content_block_delta",
                        "delta": {"type": "text_delta", "text": "hola"},
                    },
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn"},
                        "usage": {"output_tokens": 3},
                    },
                ]
            ),
        )
        p = AnthropicMessages(model="claude-x", transport=transport)
        events = await collect(p, [Message(role="user", content="hi")], [])
        assert [e.text for e in events if isinstance(e, TextDelta)] == ["hola"]
        end = events[-1]
        assert isinstance(end, MessageEnd) and end.stop_reason == "end_turn"
        assert end.usage == Usage(input_tokens=5, output_tokens=3)

    async def test_weird_stop_reason_maps_to_typed_error(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": "weird_new_thing"},
                        "usage": {},
                    }
                ]
            ),
        )
        p = AnthropicMessages(model="claude-x", transport=transport)
        end = (await collect(p, [Message(role="user", content="hi")], []))[-1]
        assert isinstance(end, MessageEnd)
        assert end.stop_reason == "error"
        assert "weird_new_thing" in (end.error or "")

    async def test_in_stream_error_event(self) -> None:
        seen, transport = capture_request()
        set_response(
            seen,
            sse_response(
                [
                    {
                        "type": "error",
                        "error": {"type": "overloaded_error", "message": "overloaded"},
                    }
                ]
            ),
        )
        p = AnthropicMessages(model="claude-x", transport=transport)
        end = (await collect(p, [Message(role="user", content="hi")], []))[-1]
        assert isinstance(end, MessageEnd) and end.stop_reason == "error"
        assert "overloaded" in (end.error or "")

    def test_tool_result_becomes_user_block(self) -> None:
        p = AnthropicMessages(model="claude-x")
        history = p._build_history(
            [
                Message(role="user", content="hi"),
                Message(
                    role="assistant",
                    tool_calls=(ToolCall(id="tu_1", name="read_file", arguments={"path": "a"}),),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id="tu_1", content="file body", is_error=False
                    ),
                ),
            ]
        )
        assert history[-1]["role"] == "user"
        block = history[-1]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "tu_1"
        assert block["content"] == "file body"

    def test_consecutive_tool_results_merge_into_one_user_message(self) -> None:
        p = AnthropicMessages(model="claude-x")
        history = p._build_history(
            [
                Message(role="user", content="hi"),
                Message(
                    role="assistant",
                    tool_calls=(
                        ToolCall(id="tu_1", name="a", arguments={}),
                        ToolCall(id="tu_2", name="b", arguments={}),
                    ),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(tool_call_id="tu_1", content="r1"),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(tool_call_id="tu_2", content="r2"),
                ),
            ]
        )
        # merged: last message has BOTH tool_result blocks (donor pattern —
        # Anthropic rejects consecutive same-role messages)
        assert history[-1]["role"] == "user"
        ids = [b["tool_use_id"] for b in history[-1]["content"]]
        assert ids == ["tu_1", "tu_2"]

    def test_orphan_tool_result_stripped(self) -> None:
        p = AnthropicMessages(model="claude-x")
        history = p._build_history(
            [
                Message(role="user", content="hi"),
                Message(
                    role="tool",
                    tool_result=ToolResult(tool_call_id="ghost", content="r"),
                ),
            ]
        )
        assert len(history) == 1  # orphan-only message dropped entirely
        assert history[0]["role"] == "user"


# --------------------------------------------------------------------------
# base.py plumbing
# --------------------------------------------------------------------------


class TestBase:
    def test_provider_protocol_runtime_check(self) -> None:
        from tlamati.providers.base import Provider

        assert isinstance(OpenAICompat(model="m"), Provider)
        assert isinstance(AnthropicMessages(model="m"), Provider)

    async def test_malformed_sse_raises_typed(self) -> None:
        from tlamati.providers.base import iter_sse

        resp = httpx.Response(200, content=b"data: {broken\n\n")
        with pytest.raises(ProviderError) as ei:
            async for _ in iter_sse(resp):
                pass
        assert ei.value.kind == "stream"
