"""SEC.2: la TUI cablea sandbox/net (el bug raíz).

Antes: tui/app.py llamaba make_tools(self.workdir) SIN flags → la red era
inalcanzable en la TUI aunque --sandbox-net existiera (mismo patrón que el
pitfall #5 de E3d con --skills-dir). Señal observable sin tocar red real:
`produces_untrusted` del tool terminal (terminal.py:104) = sandbox_net or
not sandbox.
"""

from __future__ import annotations

from typing import Any

import pytest

from tlamati.tui.app import TlamatiApp


class _FakeOpenAICompat:
    model = "fake"

    def __init__(self, model: str = "", base_url: str = "", api_key: str = "") -> None:
        pass

    async def stream(self, messages: Any, tools: Any = ()) -> Any:
        raise AssertionError("este test no corre turnos")
        yield  # pragma: no cover — generator vacío


@pytest.fixture(autouse=True)
def _fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tlamati.tui.app.OpenAICompat", _FakeOpenAICompat)
    monkeypatch.setenv("OPENROUTER_API_KEY", "***")


def _untrusted(app: TlamatiApp) -> bool | None:
    assert app.registry is not None, f"setup_error={app.setup_error}"
    tool = app.registry.get("terminal")
    assert tool is not None
    return tool.produces_untrusted


class TestTuiSandboxFlags:
    async def test_flag_explicito_net_true_llega_al_tool(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        app = TlamatiApp(
            workdir=tmp_path, session_db=str(tmp_path / "s.db"),
            sandbox=True, sandbox_net=True,
        )
        async with app.run_test():
            assert _untrusted(app) is True

    async def test_flag_explicito_net_false_con_jaula(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        app = TlamatiApp(
            workdir=tmp_path, session_db=str(tmp_path / "s.db"),
            sandbox=True, sandbox_net=False,
        )
        async with app.run_test():
            assert _untrusted(app) is False

    async def test_default_sin_flags_red_on(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """BREAKING SEC.1 visto desde la TUI: sin flags ni config, net=True."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("tlamati.tui.app.load_config", lambda: {})
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test():
            assert _untrusted(app) is True

    async def test_config_gobierna_cuando_no_hay_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "tlamati.tui.app.load_config", lambda: {"sandbox": {"net": False}}
        )
        app = TlamatiApp(workdir=tmp_path, session_db=str(tmp_path / "s.db"))
        async with app.run_test():
            assert _untrusted(app) is False

    async def test_flag_pisa_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "tlamati.tui.app.load_config", lambda: {"sandbox": {"net": False}}
        )
        app = TlamatiApp(
            workdir=tmp_path, session_db=str(tmp_path / "s.db"), sandbox_net=True
        )
        async with app.run_test():
            assert _untrusted(app) is True

    async def test_sin_jaula_terminal_libre(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """sandbox=False → produces_untrusted=True SIEMPRE (sin jaula hay red
        real, cruce de frontera aunque sandbox_net=False)."""
        monkeypatch.chdir(tmp_path)
        app = TlamatiApp(
            workdir=tmp_path, session_db=str(tmp_path / "s.db"),
            sandbox=False, sandbox_net=False,
        )
        async with app.run_test():
            assert _untrusted(app) is True
