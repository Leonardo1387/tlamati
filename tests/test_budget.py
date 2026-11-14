"""Tests for context/budget.py (A5)."""

from __future__ import annotations

from tlamati.context.budget import (
    HARD_RATIO,
    WARN_RATIO,
    Budget,
    ContextBreakdown,
    SectionCost,
    count_tokens,
)
from tlamati.core.messages import Message, ToolResult
from tlamati.providers.base import ToolSpec


class TestCountTokens:
    def test_empty_zero(self) -> None:
        assert count_tokens("") == 0

    def test_nonempty_positive(self) -> None:
        assert count_tokens("hola mundo") > 0

    def test_roughly_proportional(self) -> None:
        small = count_tokens("hola")
        big = count_tokens("hola " * 100)
        assert big > small * 10

    def test_never_zero_for_nonempty(self) -> None:
        assert count_tokens("x") >= 1


TOOL = ToolSpec(name="t", description="d", input_schema={"type": "object", "properties": {}})


class TestBreakdown:
    def test_sections_named(self) -> None:
        b = Budget(max_context_tokens=100_000)
        bd = b.breakdown("sys", [TOOL], [Message(role="user", content="hi")])
        assert [s.name for s in bd.sections] == ["system", "tools", "history"]

    def test_total_is_sum_of_enabled(self) -> None:
        bd = ContextBreakdown(
            sections=(
                SectionCost("system", 100),
                SectionCost("tools", 50),
                SectionCost("history", 25),
            ),
            max_context_tokens=1000,
        )
        assert bd.total == 175

    def test_disabled_section_not_counted(self) -> None:
        bd = ContextBreakdown(
            sections=(SectionCost("system", 100), SectionCost("tools", 50, enabled=False)),
            max_context_tokens=1000,
        )
        assert bd.total == 100

    def test_status_ok(self) -> None:
        bd = ContextBreakdown(sections=(SectionCost("system", 100),), max_context_tokens=1000)
        assert bd.status == "ok"

    def test_status_warn_at_80(self) -> None:
        bd = ContextBreakdown(
            sections=(SectionCost("system", int(800 * WARN_RATIO)),), max_context_tokens=800
        )
        assert bd.status == "warn"

    def test_status_exceeded_at_95(self) -> None:
        bd = ContextBreakdown(
            sections=(SectionCost("system", int(800 * HARD_RATIO)),), max_context_tokens=800
        )
        assert bd.status == "exceeded"

    def test_human_line_has_sections_and_pct(self) -> None:
        b = Budget(max_context_tokens=100_000)
        bd = b.breakdown("system prompt", [TOOL], [Message(role="user", content="hi")])
        h = bd.human()
        assert "system=" in h and "tools=" in h and "history=" in h and "%" in h

    def test_history_counts_tool_results(self) -> None:
        b = Budget(max_context_tokens=100_000)
        msg = Message(role="user", content="hi")
        tool_msg = Message(
            role="tool", tool_result=ToolResult(tool_call_id="c", content="x" * 4000)
        )
        bd_small = b.breakdown("s", [], [msg])
        bd_big = b.breakdown("s", [], [msg, tool_msg])
        assert bd_big.total > bd_small.total
