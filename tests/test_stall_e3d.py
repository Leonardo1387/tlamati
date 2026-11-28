"""E3d PASO B — detector de estancamiento + muro configurable (60/yolo) +
flujo "continúa"/"resumen" en la TUI. Diseño del fundador (19-nov sesión 21):
el bucle muerto se CASTIGA (corte duro + aviso), el avance real se PREGUNTA
(60 turnos y el humano decide: continuar o resumen). Todo $0: FakeProvider.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest

from tlamati.cli import build_parser, resolve_turn_limits
from tlamati.context.budget import Budget
from tlamati.core.json_events import EXIT_STALL, exit_code_for
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
    """Scripted provider (mismo patrón que test_loop.py)."""

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


class _FakeOpenAICompat(FakeProvider):
    _script: ClassVar[list[list[tuple[Any, ...]]]] = [[("text", "ok")]]

    def __init__(self, model: str = "", base_url: str = "", api_key: str = "") -> None:
        super().__init__(list(self._script))


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "buggy.py").write_text("def f():\n    return 1/0\n")
    return tmp_path


class TestStallDetector:
    async def test_identical_calls_three_turns_cuts(self, workdir: Path) -> None:
        """Mismo tool + mismos args 3 turnos seguidos → stall (no max_turns)."""
        loop = [[("tool", f"c{i}", "read_file", {"path": "buggy.py"})] for i in range(10)]
        p = FakeProvider(loop)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
            max_turns=50,
            on_event=lambda k, d: events.append((k, d)),
        )
        assert result.stop_reason == "stall"
        assert result.turns == 3
        assert result.error is not None and "bucle detectado" in result.error
        assert any(k == "stall" for k, _ in events)

    async def test_varying_args_are_progress_not_stall(self, workdir: Path) -> None:
        """Args distintos = avance real → el muro (no el detector) decide."""
        loop = [
            [("tool", f"c{i}", "read_file", {"path": "buggy.py", "offset": i + 1})]
            for i in range(10)
        ]
        p = FakeProvider(loop)
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
            max_turns=4,
        )
        assert result.stop_reason == "max_turns"
        assert result.turns == 4

    async def test_edit_same_file_different_content_is_not_stall(self, workdir: Path) -> None:
        """El patrón legítimo edit→test→edit: escribir el MISMO archivo con
        contenido DISTINTO cambia la firma → nunca cuenta como bucle."""
        p = FakeProvider(
            [
                [("tool", "c1", "write_file", {"path": "buggy.py", "content": "v1"})],
                [("tool", "c2", "write_file", {"path": "buggy.py", "content": "v2"})],
                [("tool", "c3", "write_file", {"path": "buggy.py", "content": "v3"})],
                [("text", "listo")],
            ]
        )
        result = await run_loop(
            p,
            system="s",
            user_prompt="itera",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
        )
        assert result.stop_reason == "end_turn"

    async def test_stall_zero_disables(self, workdir: Path) -> None:
        loop = [[("tool", f"c{i}", "read_file", {"path": "buggy.py"})] for i in range(10)]
        p = FakeProvider(loop)
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
            max_turns=4,
            stall_repeats=0,
        )
        assert result.stop_reason == "max_turns"

    def test_stall_exit_code(self) -> None:
        assert exit_code_for("stall") == EXIT_STALL


class TestYoloAndWall:
    async def test_yolo_zero_max_turns_runs_past_60(self, workdir: Path) -> None:
        """max_turns=0 = yolo: sin muro. 65 turnos de avance real y termina."""
        loop = [
            [("tool", f"c{i}", "read_file", {"path": "buggy.py", "offset": i + 1})]
            for i in range(65)
        ] + [[("text", "terminé")]]
        p = FakeProvider(loop)
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(10_000_000),
            max_turns=0,
        )
        assert result.stop_reason == "end_turn"
        assert result.turns == 66

    async def test_yolo_still_catches_stall(self, workdir: Path) -> None:
        """Yolo NO desactiva el detector: bucle muerto se corta igual."""
        loop = [[("tool", f"c{i}", "read_file", {"path": "buggy.py"})] for i in range(10)]
        p = FakeProvider(loop)
        result = await run_loop(
            p,
            system="s",
            user_prompt="x",
            tools=Registry(make_tools(workdir)),
            budget=Budget(100_000),
            max_turns=0,
        )
        assert result.stop_reason == "stall"


class TestResolveTurnLimits:
    def _args(self, **kw: Any) -> Any:
        ns = build_parser().parse_args(["-p", "x"])
        for k, v in kw.items():
            setattr(ns, k, v)
        return ns

    def test_defaults(self) -> None:
        assert resolve_turn_limits({}, self._args()) == (90, 3)  # T3: 60→90

    def test_flag_wins_over_config(self) -> None:
        cfg = {"general": {"max_turns": 30, "stall_repeats": 5}}
        assert resolve_turn_limits(cfg, self._args(max_turns=42)) == (42, 5)

    def test_config_over_default(self) -> None:
        cfg = {"general": {"max_turns": 0, "stall_repeats": 0}}
        assert resolve_turn_limits(cfg, self._args()) == (0, 0)  # yolo + sin detector

    def test_bad_config_falls_back(self) -> None:
        cfg = {"general": {"max_turns": "abc", "stall_repeats": None}}
        assert resolve_turn_limits(cfg, self._args()) == (90, 3)


class TestTuiWallFlow:
    """E3d PASO B en la TUI: al topar el muro NO hay frenazo seco — mensaje
    claro y el siguiente texto del usuario decide (continúa / resumen)."""

    @pytest.fixture(autouse=True)
    def _fake_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tlamati.tui.app.OpenAICompat", _FakeOpenAICompat)
        monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")

    async def test_wall_offers_continue_and_resumes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from tlamati.tui.app import TlamatiApp

        monkeypatch.chdir(tmp_path)
        # Guion: quema el muro (max_turns=2) con avance real; al reanudar,
        # termina con texto (si no, la reanudación toparía el muro otra vez).
        _FakeOpenAICompat._script = [
            [("tool", f"c{i}", "read_file", {"path": "x.py", "offset": i + 1})] for i in range(2)
        ] + [[("text", "sigo trabajando")], [("text", "terminé")]]
        (tmp_path / "x.py").write_text("x = 1\n")
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"), max_turns=2)
        async with app.run_test() as pilot:
            assert app.setup_error is None
            ta = app.query_one("#prompt")
            ta.focus()
            await pilot.press(*"trabaja")
            await pilot.press("ctrl+enter")
            await pilot.pause(0.4)
            # T3: al topar el muro AHORA se abre el modal mid-run (seguir/
            # cerrar). Elegimos cerrar → la corrida termina stop=max_turns y
            # el flujo post-muro de E3d (continúa/resumen) sigue vigente.
            await pilot.press("c")
            await pilot.pause(0.4)
            assert app._awaiting_wall_choice
            # Mensaje honesto visible en el transcript.
            transcript = " ".join(str(w.render()) for w in app.query("Static"))
            assert "continúa" in transcript and "resumen" in transcript
            # Reanudar con la historia intacta (cualquier texto reanuda;
            # "continúa" con acento no es tipeable por pilot.press → texto simple).
            history_before = len(app._history)
            assert history_before > 0
            await pilot.press(*"sigue")
            await pilot.press("ctrl+enter")
            await pilot.pause(0.4)
            assert not app._awaiting_wall_choice
            assert len(app._history) > history_before  # la historia creció, no se reinició

    async def test_wall_summary_uses_summarizer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from tlamati.tui.app import TlamatiApp

        monkeypatch.chdir(tmp_path)
        _FakeOpenAICompat._script = [
            [("tool", f"c{i}", "read_file", {"path": "x.py", "offset": i + 1})] for i in range(4)
        ]
        (tmp_path / "x.py").write_text("x = 1\n")

        calls: list[str] = []

        class _FakeSummarizer:
            async def summarize(self, transcript: str) -> tuple[str | None, Any]:
                calls.append(transcript)
                from tlamati.core.messages import Usage

                return "RESUMEN: se leyó x.py cuatro veces.", Usage(input_tokens=5, output_tokens=3)

        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"), max_turns=2)
        async with app.run_test() as pilot:
            assert app.setup_error is None
            assert app.compactor is not None
            app.compactor.summarizer = _FakeSummarizer()  # type: ignore[assignment]
            ta = app.query_one("#prompt")
            ta.focus()
            await pilot.press(*"trabaja")
            await pilot.press("ctrl+enter")
            await pilot.pause(0.4)
            # T3: cerrar el modal del muro mid-run para llegar al flujo
            # post-muro (resumen) de E3d.
            await pilot.press("c")
            await pilot.pause(0.4)
            assert app._awaiting_wall_choice
            await pilot.press(*"resumen")
            await pilot.press("ctrl+enter")
            await pilot.pause(0.4)
            assert calls, "el summarizer nunca recibió el transcript"
            assert not app._awaiting_wall_choice
            transcript = " ".join(str(w.render()) for w in app.query("Static"))
            assert "RESUMEN" in transcript or "resumen" in transcript
