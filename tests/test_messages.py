"""Tests for core/messages.py — the narrow waist."""

from __future__ import annotations

import pytest

from tlamati.core.messages import (
    Message,
    MessageEnd,
    TextDelta,
    ToolCall,
    ToolCallStart,
    ToolResult,
    Usage,
)


class TestToolCall:
    def test_defaults(self) -> None:
        tc = ToolCall(id="t1", name="read_file")
        assert tc.arguments == {}
        assert tc.raw_arguments == ""

    def test_raw_preserved(self) -> None:
        tc = ToolCall(id="t1", name="edit", arguments={"a": 1}, raw_arguments='{"a": 1}')
        assert tc.raw_arguments == '{"a": 1}'


class TestToolResult:
    def test_defaults_clean(self) -> None:
        tr = ToolResult(tool_call_id="t1", content="ok")
        assert not tr.is_error
        assert not tr.untrusted
        assert not tr.truncated


class TestMessage:
    def test_assistant_needs_content_or_tools(self) -> None:
        with pytest.raises(ValueError, match="content or tool_calls"):
            Message(role="assistant")

    def test_tool_message_needs_result(self) -> None:
        with pytest.raises(ValueError, match="tool_result"):
            Message(role="tool", content="x")

    def test_valid_assistant_with_toolcalls_empty_content(self) -> None:
        m = Message(
            role="assistant",
            tool_calls=(ToolCall(id="t1", name="terminal", arguments={"cmd": "ls"}),),
        )
        assert m.content == ""
        assert m.tool_calls[0].name == "terminal"

    def test_roundtrip_dict(self) -> None:
        m = Message(
            role="assistant",
            content="voy a leer",
            tool_calls=(
                ToolCall(
                    id="t1",
                    name="read_file",
                    arguments={"path": "a.py"},
                    raw_arguments='{"path": "a.py"}',
                ),
            ),
        )
        assert Message.from_dict(m.as_dict()) == m

    def test_roundtrip_tool_result(self) -> None:
        tr = ToolResult(
            tool_call_id="t1", content="...", is_error=True, untrusted=True, truncated=True
        )
        m = Message(role="tool", tool_result=tr)
        restored = Message.from_dict(m.as_dict())
        assert restored.tool_result == tr

    def test_ids_unique(self) -> None:
        a, b = Message(role="user", content="1"), Message(role="user", content="2")
        assert a.id != b.id


class TestUsage:
    def test_additive(self) -> None:
        u1 = Usage(input_tokens=100, output_tokens=20, cost_usd=0.01)
        u2 = Usage(input_tokens=50, output_tokens=5, cache_read_tokens=80)
        total = u1 + u2
        assert total.input_tokens == 150
        assert total.output_tokens == 25
        assert total.cache_read_tokens == 80
        assert total.cost_usd == pytest.approx(0.01)

    def test_cost_none_plus_none(self) -> None:
        assert (Usage() + Usage()).cost_usd is None

    def test_total_tokens(self) -> None:
        assert Usage(input_tokens=3, output_tokens=4).total_tokens == 7


class TestEvents:
    def test_event_shapes_frozen(self) -> None:
        td = TextDelta(text="hola")
        with pytest.raises(AttributeError):
            td.text = "adios"  # type: ignore[misc]

    def test_message_end_vocabulary(self) -> None:
        me = MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=1))
        assert me.error is None

    def test_toolcall_start(self) -> None:
        ts = ToolCallStart(id="t1", name="write_file")
        assert ts.name == "write_file"
