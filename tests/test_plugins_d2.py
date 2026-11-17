"""D2 — plugins: HookRegistry (3 hooks), descubrimiento fail-soft, veto,
plugin interno de auditoría (migración real de Registry._log), prefijo
byte-idéntico, CLI --no-plugins/--plugins-dir.

Los tests B5 (tests/test_ledger_b5.py) siguen verdes SIN cambios = prueba
de la migración (comportamiento observable idéntico).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tlamati.core.messages import ToolResult
from tlamati.plugins import HookRegistry, load_plugins
from tlamati.tools.registry import Permission, Registry, Tool


def _echo_tool(name: str = "echo", permission: Permission = Permission.AUTO) -> Tool:
    async def _run(args: dict[str, Any]) -> str:
        return f"eco: {args.get('text', '')}"

    return Tool(
        name=name,
        description="eco",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        run=_run,
        permission=permission,
    )


def _boom_tool() -> Tool:
    async def _run(args: dict[str, Any]) -> str:
        raise RuntimeError("boom")

    return Tool(name="boom", description="x", input_schema={"type": "object"}, run=_run)


class TestHookRegistry:
    def test_before_tool_veto_wins_first(self) -> None:
        h = HookRegistry()
        h.add_before_tool(lambda n, a: "no por hoy" if n == "echo" else None)
        h.add_before_tool(lambda n, a: "segundo nunca gana")
        assert h.fire_before_tool("echo", {}) == "no por hoy"

    def test_before_tool_none_passes(self) -> None:
        h = HookRegistry()
        h.add_before_tool(lambda n, a: None)
        assert h.fire_before_tool("echo", {}) is None

    def test_before_tool_exception_is_isolated(self) -> None:
        h = HookRegistry()

        def _malo(n: str, a: dict[str, Any]) -> str | None:
            raise ValueError("plugin roto")

        h.add_before_tool(_malo)
        h.add_before_tool(lambda n, a: "veto sano")
        # el hook roto no mata: el sano sigue funcionando (fail-soft)
        assert h.fire_before_tool("echo", {}) == "veto sano"

    def test_after_and_on_error_observe(self) -> None:
        h = HookRegistry()
        vistos: list[tuple[str, str]] = []
        h.add_after_tool(lambda n, a, d, r: vistos.append((n, d)))
        h.add_on_error(lambda n, a, e: vistos.append((n, str(e))))
        res = ToolResult(tool_call_id="t", content="ok", is_error=False)
        h.fire_after_tool("echo", {}, "auto", res)
        h.fire_on_error("boom", {}, RuntimeError("x"))
        assert vistos == [("echo", "auto"), ("boom", "x")]


class TestRegistryHooks:
    async def test_veto_becomes_honest_error_result(self) -> None:
        h = HookRegistry()
        h.add_before_tool(lambda n, a: "política del equipo")
        reg = Registry([_echo_tool()], hooks=h)
        res = await reg.execute("echo", {"text": "hola"}, "t1")
        assert res.is_error
        assert "vetada por plugin" in res.content
        assert "política del equipo" in res.content

    async def test_veto_cannot_approve_or_relax(self) -> None:
        # before_tool devuelve None (o lo que sea no-string) → flujo normal;
        # no existe mecanismo de aprobación: el permission gate sigue intacto.
        h = HookRegistry()
        h.add_before_tool(lambda n, a: None)
        reg = Registry([_echo_tool(permission=Permission.ASK)], hooks=h)
        res = await reg.execute("echo", {"text": "hola"}, "t1")
        assert res.is_error  # ask sin approver = error honesto (nunca yolo)
        assert "requires approval" in res.content

    async def test_on_error_observes_without_changing(self) -> None:
        h = HookRegistry()
        errores: list[str] = []
        h.add_on_error(lambda n, a, e: errores.append(f"{n}:{type(e).__name__}"))
        reg = Registry([_boom_tool()], hooks=h)
        res = await reg.execute("boom", {}, "t1")
        assert res.is_error
        assert "RuntimeError: boom" in res.content  # comportamiento intacto
        assert errores == ["boom:RuntimeError"]

    async def test_after_tool_receives_every_decision(self) -> None:
        h = HookRegistry()
        decisiones: list[str] = []
        h.add_after_tool(lambda n, a, d, r: decisiones.append(d))
        reg = Registry([_echo_tool(), _boom_tool()], hooks=h)
        await reg.execute("echo", {"text": "a"}, "t1")  # auto
        await reg.execute("noexiste", {}, "t2")  # unknown
        await reg.execute("boom", {}, "t3")  # auto (excepción interna → error honesto)
        assert decisiones == ["auto", "unknown", "auto"]


class TestLedgerMigration:
    """Migración real (consumidor #1): el plugin interno registra tool_events
    vía after_tool. Comportamiento observable idéntico a B5 (sus tests siguen
    verdes sin cambios — esta clase verifica la costura nueva)."""

    async def test_plugin_denied_lands_in_ledger(self, tmp_path: Path) -> None:
        from tlamati.policy.ledger import Ledger

        db = tmp_path / "audit.db"
        led = Ledger(db, "s-d2")
        h = HookRegistry()
        h.add_before_tool(lambda n, a: "veto")
        reg = Registry([_echo_tool()], ledger=led, hooks=h)
        await reg.execute("echo", {"text": "x"}, "t1")
        events, _ = Ledger.read_session(db, "s-d2")
        assert len(events) == 1
        assert events[0].decision == "plugin_denied"  # decisión NUEVA append-only
        assert events[0].is_error
        led.close()

    async def test_internal_audit_plugin_always_on(self, tmp_path: Path) -> None:
        from tlamati.policy.ledger import Ledger

        db = tmp_path / "audit2.db"
        led = Ledger(db, "s-d2b")
        # SIN hooks explícitos: el Registry crea su HookRegistry y registra el
        # plugin interno — la auditoría B5 no es opcional ni desactivable.
        reg = Registry([_echo_tool()], ledger=led)
        await reg.execute("echo", {"text": "x"}, "t1")
        events, _ = Ledger.read_session(db, "s-d2b")
        assert len(events) == 1
        assert events[0].decision == "auto"
        led.close()


_PLUGIN_OK = """
def register(hooks):
    hooks.add_before_tool(lambda name, args: "veto-plugin" if name == "echo" else None)
"""

_PLUGIN_SIN_REGISTER = "X = 1\n"

_PLUGIN_QUE_TRUENA = """
def register(hooks):
    raise RuntimeError("plugin con bug")
"""

_PLUGIN_ROMPE_IMPORT = "import modulo_que_no_existe_d2\n"


class TestDiscovery:
    def _write(self, d: Path, name: str, body: str) -> None:
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body)

    def test_project_and_user_and_extra_dirs(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        user = tmp_path / "user"
        extra = tmp_path / "extra"
        self._write(proj / ".tlamati" / "plugins", "uno.py", _PLUGIN_OK)
        self._write(user, "dos.py", _PLUGIN_OK)
        self._write(extra, "tres.py", _PLUGIN_OK)
        h = HookRegistry()
        rep = load_plugins(h, project_root=proj, extra_dirs=[extra], user_dir=user)
        assert sorted(rep.loaded) == ["dos", "tres", "uno"]
        assert not rep.failed

    def test_broken_plugins_fail_soft(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        plugins = proj / ".tlamati" / "plugins"
        self._write(plugins, "sin_register.py", _PLUGIN_SIN_REGISTER)
        self._write(plugins, "trueno.py", _PLUGIN_QUE_TRUENA)
        self._write(plugins, "roto.py", _PLUGIN_ROMPE_IMPORT)
        self._write(plugins, "sano.py", _PLUGIN_OK)
        h = HookRegistry()
        rep = load_plugins(h, project_root=proj, user_dir=tmp_path / "vacio")
        assert rep.loaded == ["sano"]  # el sano sobrevive — NUNCA rompe la corrida
        assert {n for n, _ in rep.failed} == {"sin_register", "trueno", "roto"}

    def test_duplicate_first_wins_with_warning(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        user = tmp_path / "user"
        self._write(proj / ".tlamati" / "plugins", "mismo.py", _PLUGIN_OK)
        self._write(user, "mismo.py", _PLUGIN_SIN_REGISTER)
        h = HookRegistry()
        rep = load_plugins(h, project_root=proj, user_dir=user)
        # orden estable: usuario va ANTES que proyecto en dirs → gana el de usuario...
        # pero el de usuario no tiene register → falla; el del proyecto carga.
        # El duplicado se detecta por NOMBRE solo entre cargados con éxito.
        assert "mismo" in rep.loaded
        assert {n for n, _ in rep.failed} == {"mismo"}

    def test_missing_dirs_are_ok(self, tmp_path: Path) -> None:
        h = HookRegistry()
        rep = load_plugins(h, project_root=tmp_path / "noexiste", user_dir=tmp_path / "tampoco")
        assert not rep.loaded
        assert not rep.failed

    def test_entry_points_discovered(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib.metadata as md

        class FakeEP:
            name = "ep_plugin"

            def load(self) -> Any:
                import types

                mod = types.ModuleType("ep_plugin")

                def register(hooks: HookRegistry) -> None:
                    hooks.add_before_tool(lambda n, a: None)

                mod.register = register  # type: ignore[attr-defined]
                return mod

        monkeypatch.setattr(md, "entry_points", lambda group: [FakeEP()])
        h = HookRegistry()
        rep = load_plugins(h, project_root=tmp_path, user_dir=tmp_path)
        assert rep.loaded == ["ep_plugin"]


class TestPrefixCache:
    """Los plugins NO tocan el prefijo (invisibles al modelo): el system
    prompt es byte-idéntico con y sin hooks (cache sagrada, donor C6)."""

    async def test_specs_unaffected_by_hooks(self) -> None:
        tools = [_echo_tool(), _boom_tool()]
        reg_sin = Registry([t for t in tools])
        h = HookRegistry()
        h.add_before_tool(lambda n, a: None)
        h.add_after_tool(lambda n, a, d, r: None)
        reg_con = Registry([t for t in tools], hooks=h)
        assert reg_sin.specs() == reg_con.specs()  # wire idéntico


class TestCliFlags:
    def test_parser_accepts_plugin_flags(self) -> None:
        from tlamati.cli import build_parser

        p = build_parser()
        args = p.parse_args(["-p", "x", "--no-plugins"])
        assert args.no_plugins is True
        args2 = p.parse_args(["-p", "x", "--plugins-dir", "/a", "--plugins-dir", "/b"])
        assert args2.plugins_dir == ["/a", "/b"]
