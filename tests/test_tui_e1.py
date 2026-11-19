"""E1: TUI Textual — tests headless con run_test()/Pilot (sin terminal real).

Textual trae su propio "driver virtual": app.run_test() levanta la app en
memoria y Pilot simula teclas/clics. Todo $0: FakeProvider scripted, sin red.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest

from tlamati.core.messages import Event, Message, MessageEnd, TextDelta, Usage
from tlamati.providers.base import ToolSpec
from tlamati.tui.app import ApproveScreen, TlamatiApp, build_diff_preview


class FakeProvider:
    """Scripted (patrón test_loop.py)."""

    model = "fake"

    def __init__(self, turns: list[list[tuple[Any, ...]]]) -> None:
        self.turns = turns

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        script = self.turns.pop(0) if self.turns else [("text", "fin")]
        for step in script:
            if step[0] == "text":
                yield TextDelta(text=str(step[1]))
        yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))


class _FakeOpenAICompat(FakeProvider):
    _script: ClassVar[list[list[tuple[Any, ...]]]] = [[("text", "**hola** desde tlamati")]]

    def __init__(self, model: str = "", base_url: str = "", api_key: str = "") -> None:
        super().__init__(list(self._script))


@pytest.fixture(autouse=True)
def _fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tlamati.tui.app.OpenAICompat", _FakeOpenAICompat)
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")


class TestDiffPreview:
    def test_write_file_new_file_all_added(self, tmp_path: Path) -> None:
        d = build_diff_preview(
            "write_file", {"path": str(tmp_path / "nuevo.py"), "content": "x = 1\ny = 2\n"}
        )
        assert d.startswith("---")
        assert "+x = 1" in d and "+y = 2" in d

    def test_write_file_existing_shows_delta(self, tmp_path: Path) -> None:
        p = tmp_path / "f.py"
        p.write_text("a = 1\nb = 2\n")
        d = build_diff_preview("write_file", {"path": str(p), "content": "a = 1\nb = 3\n"})
        assert "-b = 2" in d and "+b = 3" in d

    def test_edit_shows_replacement(self, tmp_path: Path) -> None:
        p = tmp_path / "g.py"
        p.write_text("viejo = True\n")
        d = build_diff_preview(
            "edit", {"path": str(p), "old_string": "viejo", "new_string": "nuevo"}
        )
        assert "-viejo = True" in d and "+nuevo = True" in d

    def test_unknown_tool_falls_back_to_args(self) -> None:
        d = build_diff_preview("terminal", {"command": "ls -la"})
        assert "ls -la" in d and d.startswith("{")

    def test_long_args_truncated(self) -> None:
        d = build_diff_preview("terminal", {"command": "x" * 5000})
        assert len(d) <= 4000


class TestApproveScreen:
    async def test_verdicts_via_dismiss(self) -> None:
        """push_screen_wait recibe el veredicto del dismiss (contrato real
        del approver: once/always/reject)."""
        from textual import work
        from textual.app import App as _App

        def _make_host(verdict: dict[str, str | None]) -> type[_App[None]]:
            class _Host(_App[None]):
                def on_mount(self) -> None:
                    self._ask_worker = self._ask()

                @work
                async def _ask(self) -> None:
                    # push_screen_wait SOLO corre dentro de un worker (Textual).
                    verdict["v"] = await self.push_screen_wait(
                        ApproveScreen("write_file", "diff...")
                    )

            return _Host

        for btn_id, esperado in (
            ("b-once", "once"),
            ("b-always", "always"),
            ("b-reject", "reject"),
        ):
            verdict: dict[str, str | None] = {"v": None}
            host = _make_host(verdict)()
            async with host.run_test() as pilot:
                await pilot.pause()
                await pilot.click(f"#{btn_id}")
                await pilot.pause()
            assert verdict["v"] == esperado


class TestAppFlow:
    async def test_setup_error_without_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setattr("tlamati.tui.app.load_config", lambda: {})
        monkeypatch.setattr("tlamati.tui.app._resolve_api_key", lambda cfg: "")
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test():
            assert app.setup_error is not None and "API key" in app.setup_error

    async def test_prompt_roundtrip_renders_markdown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _FakeOpenAICompat._script = [[("text", "**respuesta** del modelo")]]
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test() as pilot:
            assert app.setup_error is None
            ta = app.query_one("#prompt")
            ta.focus()
            await pilot.press(*"hola")
            await pilot.press("ctrl+enter")
            await pilot.pause(0.3)
            # El stream terminó: hay un widget Markdown con el texto del modelo.
            from textual.widgets import Markdown as Md

            mds = app.query(Md)
            assert len(mds) >= 1
            assert "respuesta" in mds[0].source
            # La barra de contexto se actualizó (costo visible, PRD §5).
            bar = str(app.query_one("#ctxbar").render())
            assert "ctx:" in bar

    async def test_history_persisted_multi_turn(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _FakeOpenAICompat._script = [
            [("text", "primera")],
            [("text", "segunda")],
        ]
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test() as pilot:
            for msg in ("uno", "dos"):
                ta = app.query_one("#prompt")
                ta.focus()
                await pilot.press(*msg)
                await pilot.press("ctrl+enter")
                await pilot.pause(0.3)
            roles = [m.role for m in app._history]
            # user, assistant, user, assistant = conversación multi-turno real.
            assert roles == ["user", "assistant", "user", "assistant"]

    async def test_stream_burst_no_lost_deltas(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """REGRESIÓN (bug real del smoke E1): deltas emitidos SIN pausa
        entre ellos corrompían el Markdown final si update() se llamaba por
        delta (AwaitCompletes concurrentes). Con el throttle del timer el
        texto final debe estar COMPLETO."""
        monkeypatch.chdir(tmp_path)
        _FakeOpenAICompat._script = [
            [("text", "PRIMERO ")]
            + [("text", f"SEGUNDO{i} ") for i in range(50)]
            + [("text", "TERCERO")],
        ]
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test() as pilot:
            ta = app.query_one("#prompt")
            ta.focus()
            await pilot.press(*"x")
            await pilot.press("ctrl+enter")
            await pilot.pause(0.5)
            from textual.widgets import Markdown as Md

            mds = app.query(Md)
            assert len(mds) >= 1
            assert mds[0].source.endswith("TERCERO")
            assert mds[0].source.startswith("PRIMERO")

    async def test_approver_reject_denies_tool(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """El approver de la TUI es el canal real de ASK (B4 lo prometía):
        rechazo en el modal → la tool NO corre (fail closed)."""
        monkeypatch.chdir(tmp_path)
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test():
            assert app.registry is not None

            async def _fake_wait(screen: Any) -> str:
                return "reject"

            monkeypatch.setattr(app, "push_screen_wait", _fake_wait)
            from tlamati.tools.registry import Permission, Tool

            async def _bang(args: dict[str, Any]) -> str:
                raise AssertionError("una tool rechazada NUNCA debe correr")

            ask_tool = Tool(
                name="cosapeligrosa",
                description="x",
                input_schema={"type": "object"},
                run=_bang,
                permission=Permission.ASK,
            )
            app.registry.register(ask_tool)
            res = await app.registry.execute("cosapeligrosa", {}, "t1")
            assert res.is_error

            async def _fake_always(screen: Any) -> str:
                return "always"

            monkeypatch.setattr(app, "push_screen_wait", _fake_always)
            ok = await app._approver("otra_tool", {})
            assert ok is True and "otra_tool" in app._always_allow
            assert await app._approver("otra_tool", {}) is True  # sin modal 2ª vez


class TestCliGate:
    def test_no_tty_prints_help_not_tui(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contrato CI: sin tty, `tlamati` (sin args) sigue imprimiendo help
        y NUNCA intenta arrancar la TUI (exit 0)."""
        from tlamati.cli import main

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert main([]) == 0
        assert "usage" in capsys.readouterr().out

    def test_tty_without_textual_gives_install_hint(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """textual ausente → error honesto con instrucción de instalación
        (extra opcional, decisión #4 del fundador)."""
        import builtins

        real_import = builtins.__import__

        def _no_textual(name: str, *a: Any, **k: Any) -> Any:
            if name == "textual":
                raise ImportError("no textual")
            return real_import(name, *a, **k)

        from tlamati.tui.app import run_tui

        monkeypatch.setattr(builtins, "__import__", _no_textual)
        assert run_tui() == 2
        assert "tlamati[tui]" in capsys.readouterr().err


class TestTuiSkillsE3d:
    """E3d PASO A: la TUI ve las skills (antes ignoraba --skills-dir —
    causa madre del dogfooding reprobado, sesión 20)."""

    def _make_skill(self, root: Path, name: str) -> None:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: skill de prueba {name}\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    async def test_extra_skills_dir_visible_in_prompt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        extra = tmp_path / "mis-skills"
        self._make_skill(extra, "deploy-extra")
        app = TlamatiApp(
            workdir=tmp_path,
            session_db=str(tmp_path / "s.db"),
            skills_extra_dirs=[extra],
        )
        async with app.run_test():
            assert app.setup_error is None
            assert "# SKILLS" in app._system_prompt
            assert "deploy-extra" in app._system_prompt

    async def test_hermes_root_zero_ceremony(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Ceremonia cero (opción A del fundador): ~/.hermes/skills existe →
        la TUI la ve SIN ningún flag."""
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "home"
        self._make_skill(fake_home / ".hermes" / "skills", "hermes-auto")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test():
            assert app.setup_error is None
            assert "hermes-auto" in app._system_prompt

    async def test_sin_raices_prefijo_sin_bloque_skills(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Sin flag y sin ~/.hermes/skills → prefijo sin # SKILLS (invariante
        pre-E3d: la corrida no cambia cuando no hay nada que cargar)."""
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test():
            assert app.setup_error is None
            assert "# SKILLS" not in app._system_prompt
