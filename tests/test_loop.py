"""Tests for core/loop.py (A4) with a deterministic FakeProvider — zero network."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.core.loop import run_loop
from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.providers.base import ToolSpec
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry


class FakeProvider:
    """Scripted provider: each call to stream() pops the next turn script.

    A turn script step is either ("text", str) or ("tool", id, name, args_dict)
    followed by an implicit MessageEnd."""

    model = "fake"

    def __init__(self, turns: list[list[tuple[Any, ...]]]) -> None:
        self.turns = turns
        self.calls: list[list[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.calls.append(list(messages))
        script = self.turns.pop(0) if self.turns else [("text", "fin")]
        has_tools = False
        for step in script:
            if step[0] == "text":
                yield TextDelta(text=str(step[1]))
            elif step[0] == "tool":
                tid, name, args = str(step[1]), str(step[2]), step[3]
                yield ToolCallStart(id=tid, name=name)
                yield ToolCallArgsDelta(id=tid, args_json=json.dumps(args))
                has_tools = True
        yield MessageEnd(
            stop_reason="tool_use" if has_tools else "end_turn",
            usage=Usage(input_tokens=10, output_tokens=5),
        )


class ErrorProvider(FakeProvider):
    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        yield MessageEnd(stop_reason="error", error="fake provider failure")


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "buggy.py").write_text("def f():\n    return 1/0\n")
    return tmp_path


class TestRunLoop:
    async def test_plain_text_end_turn(self, workdir: Path) -> None:
        p = FakeProvider([[("text", "hola")]])
        result = await run_loop(
            p,
            system="s",
            user_prompt="hi",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
        )
        assert result.stop_reason == "end_turn"
        assert result.final_text == "hola"
        assert result.turns == 1
        assert result.usage.input_tokens == 10

    async def test_tool_roundtrip_fixes_bug(self, workdir: Path) -> None:
        """THE Phase-A demo shape: read file → write fixed file → done."""
        target = workdir / "buggy.py"
        p = FakeProvider(
            [
                [("tool", "c1", "read_file", {"path": "buggy.py"})],
                [
                    (
                        "tool",
                        "c2",
                        "write_file",
                        {"path": "buggy.py", "content": "def f():\n    return 0\n"},
                    )
                ],
                [("text", "TERMINADO: arreglé la división por cero")],
            ]
        )
        events: list[str] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="arregla el bug de buggy.py",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
            on_event=lambda k, d: events.append(k),
        )
        assert result.stop_reason == "end_turn"
        assert result.turns == 3
        assert "return 0" in target.read_text()
        # transcript: the SECOND provider call carries the tool result of the first
        second_call = p.calls[1]
        tool_msgs = [m for m in second_call if m.role == "tool"]
        assert tool_msgs and "1|" in tool_msgs[0].tool_result.content  # type: ignore[union-attr]
        assert "tool_run" in events and "budget" in events

    async def test_unknown_tool_degrades_to_error_result(self, workdir: Path) -> None:
        p = FakeProvider(
            [
                [("tool", "c1", "no_existe", {})],
                [("text", "ok")],
            ]
        )
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
        )
        tool_msg = next(m for m in p.calls[1] if m.role == "tool")
        assert tool_msg.tool_result is not None
        assert tool_msg.tool_result.is_error
        assert "unknown tool" in tool_msg.tool_result.content
        assert result.stop_reason == "end_turn"

    async def test_max_turns_stops(self, workdir: Path) -> None:
        forever = [[("tool", f"c{i}", "read_file", {"path": "buggy.py"})] for i in range(10)]
        p = FakeProvider(forever)
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
            max_turns=3,
        )
        assert result.stop_reason == "max_turns"
        assert result.turns == 3

    async def test_budget_exceeded_stops_before_spending(self, workdir: Path) -> None:
        p = FakeProvider([[("text", "nunca debe correr")]])
        result = await run_loop(
            p,
            system="s" * 50_000,
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100),  # ridículamente chico → exceeded inmediato
        )
        assert result.stop_reason == "budget_exceeded"
        assert len(p.calls) == 0  # NO se gastó una llamada al proveedor

    async def test_provider_error_maps_to_result(self, workdir: Path) -> None:
        p = ErrorProvider([])
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
        )
        assert result.stop_reason == "error"
        assert "fake provider failure" in (result.error or "")

    async def test_interjection_enters_next_turn(self, workdir: Path) -> None:
        """Simulate Ctrl-C: send ourselves SIGINT once the loop installed its
        handler; the pending interjection must enter the NEXT turn's history
        as a user message (never mid-stream)."""
        import asyncio
        import signal

        p = FakeProvider(
            [
                [("tool", "c1", "read_file", {"path": "buggy.py"})],
                [("text", "recibí tu mensaje")],
            ]
        )

        async def interrupt_soon() -> None:
            # Espera a que run_loop haya instalado SU handler (distinto del default)
            for _ in range(200):
                if signal.getsignal(signal.SIGINT) not in (
                    signal.default_int_handler,
                    signal.SIG_DFL,
                ):
                    os.kill(os.getpid(), signal.SIGINT)
                    return
                await asyncio.sleep(0.005)
            raise AssertionError("loop never installed a SIGINT handler")

        task = asyncio.ensure_future(
            run_loop(
                p,
                system="s",
                user_prompt="x",
                tools=Registry(make_tools(workdir)),
                budget=Budget(100_000),
            )
        )
        interrupter = asyncio.ensure_future(interrupt_soon())
        result = await task
        await interrupter
        # la interjección debió entrar como mensaje user en el segundo turno
        interjections = [
            m
            for call in p.calls[1:]
            for m in call
            if m.role == "user" and "INTERRUPCIÓN" in m.content
        ]
        assert interjections, "la interjección SIGINT no llegó al siguiente turno"
        assert result.stop_reason == "end_turn"
