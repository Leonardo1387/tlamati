"""T3 — max_turns 90 + muro interactivo (HANDOFF_DOGFOOD_27NOV §T3).

Invariantes:
1. Default 60→90 coherente (loop, cli.resolve_turn_limits, TUI, README).
2. Al topar el muro: evento turn_limit_reached con el conteo; sin handler
   (headless) → cierre honesto stop=max_turns, NUNCA colgar.
3. Handler "seguir N" → extiende el tope DENTRO de la misma corrida:
   LoopState intacto — la ventana cuasi-stall (T1) y el detector exacto NO
   se reinician (exigencia explícita del handoff: no usar la extensión para
   evadir detectores).
4. Handler "cerrar" (≤0) → stop=max_turns igual que headless.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.core.loop import QuasiStallConfig, run_loop
from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.providers.base import ToolSpec
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry


class NeverEndProvider:
    """Nunca hace end_turn: tool calls infinitos con args DISTINTOS (el
    detector exacto no dispara; solo el muro puede parar la corrida)."""

    model = "never-end"

    def __init__(self, max_calls: int = 200) -> None:
        self.max_calls = max_calls
        self.n = 0

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.n += 1
        if self.n > self.max_calls:
            raise AssertionError("el loop no respetó el muro")
        tid = f"c{self.n}"
        # offset único por turno: avance "real", cero cuasi-repetición.
        yield ToolCallStart(id=tid, name="read_file")
        yield ToolCallArgsDelta(
            id=tid, args_json=json.dumps({"path": "a.txt", "offset": self.n * 7})
        )
        yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))


class LoopingProvider:
    """Args CUASI-idénticos cada turno (mutación de dígitos): topar el muro
    extendido NO debe reiniciar la ventana cuasi-stall."""

    model = "looping"

    def __init__(self) -> None:
        self.n = 0

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.n += 1
        tid = f"c{self.n}"
        yield ToolCallStart(id=tid, name="read_file")
        # timeout mutando: firma exacta distinta (detector E3d no dispara)
        # pero firma normalizada idéntica (T1 sí la ve).
        yield ToolCallArgsDelta(
            id=tid, args_json=json.dumps({"path": "a.txt", "timeout": 90 + self.n})
        )
        yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text("línea\n" * 200)
    return tmp_path


class TestDefault90:
    def test_resolve_turn_limits_default(self) -> None:
        from tlamati.cli import build_parser, resolve_turn_limits

        ns = build_parser().parse_args(["-p", "x"])
        assert resolve_turn_limits({}, ns) == (90, 3)

    def test_run_loop_default_signature(self) -> None:
        import inspect

        from tlamati.core.loop import run_loop as rl

        assert inspect.signature(rl).parameters["max_turns"].default == 90

    def test_tui_defaults(self) -> None:
        import inspect

        from tlamati.tui.app import TlamatiApp, run_tui

        assert inspect.signature(TlamatiApp.__init__).parameters["max_turns"].default == 90
        assert inspect.signature(run_tui).parameters["max_turns"].default == 90


class TestWallHeadless:
    async def test_turn_limit_reached_event_y_cierre_honesto(self, workdir: Path) -> None:
        p = NeverEndProvider()
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(1_000_000),
            max_turns=7,
            stall_repeats=0,
            on_event=lambda k, d: events.append((k, d)),
            # sin turn_limit_ask → headless: NUNCA colgar
        )
        assert result.stop_reason == "max_turns"
        assert result.turns == 7
        reached = [d for k, d in events if k == "turn_limit_reached"]
        assert len(reached) == 1
        assert reached[0] == {"turns": 7, "max_turns": 7}
        assert not [e for e in events if e[0] == "turn_limit_extended"]


class TestWallInteractive:
    async def test_seguir_extiende_y_termina_en_120(self, workdir: Path) -> None:
        """'seguir 30 más' una vez: muro a 90 → continúa hasta 120."""
        p = NeverEndProvider()
        events: list[tuple[str, dict[str, Any]]] = []
        asked: list[int] = []

        async def ask(turns: int) -> int:
            asked.append(turns)
            return 30 if len(asked) == 1 else 0

        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(1_000_000),
            max_turns=90,
            stall_repeats=0,
            turn_limit_ask=ask,
            on_event=lambda k, d: events.append((k, d)),
        )
        assert asked == [90, 120]
        assert result.stop_reason == "max_turns"
        assert result.turns == 120
        extended = [d for k, d in events if k == "turn_limit_extended"]
        assert extended == [{"extra": 30, "max_turns": 120}]

    async def test_cerrar_es_igual_que_headless(self, workdir: Path) -> None:
        p = NeverEndProvider()

        async def ask(turns: int) -> int:
            return 0

        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(1_000_000),
            max_turns=5,
            stall_repeats=0,
            turn_limit_ask=ask,
        )
        assert result.stop_reason == "max_turns" and result.turns == 5

    async def test_handler_con_basura_cierra_honesto(self, workdir: Path) -> None:
        p = NeverEndProvider()

        async def ask(turns: int) -> Any:
            return "treinta"  # tipo inválido → 0, cierre honesto

        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(1_000_000),
            max_turns=4,
            stall_repeats=0,
            turn_limit_ask=ask,
        )
        assert result.stop_reason == "max_turns" and result.turns == 4


class TestExtensionNoEvadeDetectors:
    async def test_cuasi_stall_sobrevive_extension_del_muro(self, workdir: Path) -> None:
        """REQUISITO DEL HANDOFF: 'seguir' al topar max_turns NO limpia la
        ventana cuasi-stall. Con muro corto + extensión, el detector T1 debe
        seguir contando y cortar por stall (ask_count) pese al muro nuevo."""
        p = LoopingProvider()
        events: list[tuple[str, dict[str, Any]]] = []

        async def ask_turns(turns: int) -> int:
            return 50  # siempre concede más turnos

        async def ask_quasi(matches: int) -> str:
            return "parar"  # el usuario ve el bucle y corta

        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(1_000_000),
            max_turns=4,  # muro corto para forzar la extensión rápido
            stall_repeats=0,  # args mutan: el detector exacto no aplica
            quasi_stall=QuasiStallConfig(similarity=0.85, window=15, warn_count=3, ask_count=6),
            quasi_ask=ask_quasi,
            turn_limit_ask=ask_turns,
            on_event=lambda k, d: events.append((k, d)),
        )
        # La extensión ocurrió (muro 4 → al menos una vez)…
        assert [e for e in events if e[0] == "turn_limit_extended"]
        # …y AUN ASÍ el cuasi-stall siguió vivo: cortó por stall, no por muro.
        assert result.stop_reason == "stall"
        assert [e for e in events if e[0] == "quasi_stall_ask"]

    async def test_detector_exacto_sobrevive_extension(self, workdir: Path) -> None:
        """Mismo principio con el detector EXACTO: args idénticos tras la
        extensión → stall duro (la extensión no reinicia repeat_count)."""

        class SameArgsProvider:
            model = "same-args"

            def __init__(self) -> None:
                self.n = 0

            async def stream(
                self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
            ) -> AsyncIterator[Event]:
                self.n += 1
                tid = f"c{self.n}"
                yield ToolCallStart(id=tid, name="read_file")
                yield ToolCallArgsDelta(id=tid, args_json=json.dumps({"path": "a.txt"}))
                yield MessageEnd(
                    stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5)
                )

        async def ask_turns(turns: int) -> int:
            return 10

        result = await run_loop(
            SameArgsProvider(),
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(1_000_000),
            max_turns=2,
            stall_repeats=3,
            turn_limit_ask=ask_turns,
        )
        assert result.stop_reason == "stall"
        assert result.error and "bucle detectado" in result.error
