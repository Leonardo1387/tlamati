"""D2 — plugins: everything-plugin con regla anti-speculative (F11, PRD SHOULD).

HookRegistry con SOLO 3 hooks, cada uno con consumidor concreto:

- ``before_tool(name, args) -> str | None``: se dispara en Registry.execute
  ANTES del permission gate. Puede VETAR devolviendo un string de error
  (→ ToolResult is_error honesto, decisión ledger ``plugin_denied`` — la
  lista de decisiones es append-only). NUNCA puede APROBAR ni relajar:
  policy nunca relaja (invariante B4 — un plugin solo ENDURECE).
- ``after_tool(name, args, decision, result)``: se dispara TRAS la ejecución
  (o tras la decisión deny/ask_*). Es el punto donde el plugin interno de
  auditoría registra tool_events (migración real de Registry._log, B5).
- ``on_error(name, args, exception)``: cuando tool.run lanza. OBSERVA, no
  cambia el comportamiento (el Registry ya convierte en resultado honesto).

Descubrimiento en 3 fuentes, orden estable (duplicados: primero gana + aviso
honesto, donor C3 skills):

1. entry-point ``tlamati.plugins`` (importlib.metadata, stdlib — cero deps).
2. ``~/.config/tlamati/plugins/*.py`` (usuario).
3. ``.tlamati/plugins/*.py`` (proyecto) + dirs extra del CLI (--plugins-dir).

Plugin = módulo Python con función ``register(hooks)``. Carga FAIL-SOFT:
plugin roto (import error, sin register, register que lanza) = aviso honesto
por stderr + seguir sin él, NUNCA romper la corrida (patrón skills C3,
routing C6).

SEGURIDAD: los plugins corren SIN sandbox — son código del dueño de la
máquina (mismo modelo que hermes). Ver SECURITY.md.

Los plugins NO añaden nada al system prompt (no son visibles al modelo en
D2): el prefijo cacheable es byte-idéntico con y sin plugins (cache sagrada).
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tlamati.core.messages import ToolResult

ENTRY_POINT_GROUP = "tlamati.plugins"

# Tipos de hook (sync: el consumidor concreto — ledger sqlite — es sync;
# regla anti-speculative, no inventar variantes async sin consumidor).
BeforeToolHook = Callable[[str, dict[str, Any]], str | None]
AfterToolHook = Callable[[str, dict[str, Any], str, ToolResult], None]
OnErrorHook = Callable[[str, dict[str, Any], Exception], None]


def _warn(msg: str) -> None:
    print(f"[plugins] {msg}", file=sys.stderr)


class HookRegistry:
    """Registro de los 3 (y solo 3) hooks. Fail-soft total: un hook que lanza
    se reporta honesto por stderr y la corrida sigue — un plugin NUNCA rompe
    el harness."""

    def __init__(self) -> None:
        self._before: list[BeforeToolHook] = []
        self._after: list[AfterToolHook] = []
        self._error: list[OnErrorHook] = []

    def add_before_tool(self, fn: BeforeToolHook) -> None:
        self._before.append(fn)

    def add_after_tool(self, fn: AfterToolHook) -> None:
        self._after.append(fn)

    def add_on_error(self, fn: OnErrorHook) -> None:
        self._error.append(fn)

    def fire_before_tool(self, name: str, args: dict[str, Any]) -> str | None:
        """Primer veto no vacío gana (la escalera solo endurece)."""
        for fn in self._before:
            try:
                veto = fn(name, args)
            except Exception as e:
                _warn(f"hook before_tool lanzó ({type(e).__name__}: {e}) — ignorado")
                continue
            if isinstance(veto, str) and veto.strip():
                return veto
        return None

    def fire_after_tool(
        self, name: str, args: dict[str, Any], decision: str, result: ToolResult
    ) -> None:
        for fn in self._after:
            try:
                fn(name, args, decision, result)
            except Exception as e:
                _warn(f"hook after_tool lanzó ({type(e).__name__}: {e}) — ignorado")

    def fire_on_error(self, name: str, args: dict[str, Any], exc: Exception) -> None:
        for fn in self._error:
            try:
                fn(name, args, exc)
            except Exception as e:
                _warn(f"hook on_error lanzó ({type(e).__name__}: {e}) — ignorado")


@dataclass
class PluginReport:
    """Evidencia honesta de la carga (para el log del CLI y tests)."""

    loaded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (nombre, motivo)
    duplicates: list[str] = field(default_factory=list)


def default_user_plugin_dir() -> Path:
    return Path.home() / ".config" / "tlamati" / "plugins"


def load_plugins(
    hooks: HookRegistry,
    *,
    project_root: Path,
    extra_dirs: Sequence[Path] = (),
    user_dir: Path | None = None,
) -> PluginReport:
    """Descubre y registra plugins en orden estable. Fail-soft: cada fallo se
    anota en el reporte + aviso por stderr; la corrida sigue sin el plugin."""
    report = PluginReport()
    seen: dict[str, str] = {}

    def _register_module(mod: Any, name: str, source: str) -> None:
        if name in seen:
            report.duplicates.append(name)
            _warn(f"plugin duplicado {name!r} ({source}) — gana el primero ({seen[name]})")
            return
        register = getattr(mod, "register", None)
        if not callable(register):
            report.failed.append((name, "el módulo no define register(hooks)"))
            _warn(f"plugin {name!r} ({source}) ignorado: no define register(hooks)")
            return
        try:
            register(hooks)
        except Exception as e:
            report.failed.append((name, f"register lanzó {type(e).__name__}: {e}"))
            _warn(f"plugin {name!r} ({source}) falló al registrarse: {type(e).__name__}: {e}")
            return
        seen[name] = source
        report.loaded.append(name)

    # 1. Entry-points (paquetes instalados).
    try:
        eps = list(importlib.metadata.entry_points(group=ENTRY_POINT_GROUP))
    except Exception as e:  # importlib.metadata no debería fallar; honesto igual
        eps = []
        _warn(f"entry_points({ENTRY_POINT_GROUP!r}) falló: {type(e).__name__}: {e}")
    for ep in eps:
        try:
            mod = ep.load()
        except Exception as e:
            report.failed.append((ep.name, f"import falló: {type(e).__name__}: {e}"))
            _warn(f"plugin {ep.name!r} (entry-point) no importó: {type(e).__name__}: {e}")
            continue
        _register_module(mod, ep.name, "entry-point")

    # 2+3. Dirs de usuario, proyecto y extras del CLI (orden estable, *.py sorted).
    udir = user_dir if user_dir is not None else default_user_plugin_dir()
    dirs = [udir, project_root / ".tlamati" / "plugins", *extra_dirs]
    for d in dirs:
        try:
            files = sorted(p for p in d.glob("*.py") if p.is_file()) if d.is_dir() else []
        except OSError as e:
            _warn(f"directorio {d} ilegible ({e}) — omitido")
            continue
        for path in files:
            name = path.stem
            source = str(path)
            if name in seen:
                report.duplicates.append(name)
                _warn(f"plugin duplicado {name!r} ({source}) — gana el primero ({seen[name]})")
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"_tlamati_plugin_{name}", path)
                if spec is None or spec.loader is None:
                    raise ImportError("spec_from_file_location devolvió None")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            except Exception as e:
                report.failed.append((name, f"import falló: {type(e).__name__}: {e}"))
                _warn(f"plugin {name!r} ({source}) no importó: {type(e).__name__}: {e}")
                continue
            _register_module(mod, name, source)

    return report
