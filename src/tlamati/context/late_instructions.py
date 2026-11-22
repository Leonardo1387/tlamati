"""NIVEL 1a — inyección tardía de instrucciones de repo (dogfood #6).

Causa raíz del dogfood #6: la sesión arrancó desde ~ (home), el cargador C4
camina del cwd al primer ancestro .git y no encontró nada — las reglas del
repo (AGENTS.md de [REDACTED_PROYECTO]) NUNCA llegaron al contexto del agente.

Fix: cuando el agente TOCA archivos dentro de un repo (write_file/edit, o
terminal con ``cd``), se detecta el repo (primer ancestro .git del path
tocado) y se inyectan SUS instrucciones como RECORDATORIO adjunto al tool
result — un mensaje NUEVO en la conversación, NUNCA una mutación del prefijo
(restricción sagrada STABILITY.md v0.1: el prefijo cacheable es byte-estable).

Reglas:
- Advisory, nunca bloqueante: sin AGENTS.md/CLAUDE.md en el repo → silencio.
- Sin repo (ningún ancestro .git) → silencio.
- Dedup por versión de contenido (sha256[:12] de C4): la misma versión se
  inyecta UNA vez por corrida; si el archivo cambia, la versión cambia y se
  re-inyecta (honesto: el agente ve el update).
- Las versiones ya presentes en el prefijo (sesión arrancada DENTRO del repo)
  se conocen de antemano → nunca se duplican.
- Reusa load_instructions()/render_for_prompt() de C4 byte-estable.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tlamati.context.instructions import load_instructions, render_for_prompt

# Tools que "tocan" archivos según el handoff (edit/write_file/terminal cd).
# El conocimiento de qué tools cuentan vive AQUÍ, no en el Registry.
_TOUCH_TOOLS = frozenset({"write_file", "edit", "terminal"})

# Heurística honesta de ``cd <path>`` en comandos shell (POSIX + bash):
# no parseamos shell completo — extraemos los destinos de cd y los probamos.
_CD_RE = re.compile(r"\bcd\s+(--[^\s;&|]+\s+)*([^\s;&|()]+)")


class LateInstructions:
    """Detecta repos tocados durante la corrida e inyecta sus reglas una vez.

    Estado mutable por corrida (como Policy): ``_injected`` guarda versiones
    ya vistas. Se crea uno por run y se inyecta al Registry.
    """

    def __init__(self, workdir: Path, prefix_versions: frozenset[str] = frozenset()) -> None:
        self.workdir = workdir
        self._injected: set[str] = set(prefix_versions)

    # ---------------------------------------------------------------- API
    def reminder(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Texto del recordatorio a adjuntar al tool result, o None (silencio).

        El Registry lo llama TRAS ejecutar el tool (el path fue tocado aunque
        la escritura fallara). Nunca lanza: cualquier error → None honesto
        (advisory no rompe la corrida — filosofía M8).
        """
        if tool_name not in _TOUCH_TOOLS:
            return None
        try:
            paths = self._touched_paths(tool_name, args)
            for p in paths:
                text = self._reminder_for_path(p)
                if text is not None:
                    return text
        except Exception:
            return None  # advisory: jamás romper el loop por un recordatorio
        return None

    # ------------------------------------------------------------- interno
    def _touched_paths(self, tool_name: str, args: dict[str, Any]) -> list[Path]:
        """Paths resueltos que el tool tocó (file tools: ``path``; terminal:
        destinos de ``cd``). Rutas relativas se resuelven contra workdir."""
        out: list[Path] = []
        if tool_name == "terminal":
            cmd = str(args.get("command", ""))
            for m in _CD_RE.finditer(cmd):
                raw = m.group(2).strip("'\"")
                if not raw or raw == "-":
                    continue  # cd sin argumento / cd - (stack): no hay path
                out.append(self._resolve(raw))
        else:  # write_file / edit
            raw = args.get("path")
            if isinstance(raw, str) and raw:
                out.append(self._resolve(raw))
        return out

    def _resolve(self, path_str: str) -> Path:
        from tlamati.tools.winpath import normalize_win_path

        p = Path(normalize_win_path(path_str)).expanduser()
        if not p.is_absolute():
            p = self.workdir / p
        return p.resolve()

    def _repo_root(self, path: Path) -> Path | None:
        """Primer ancestro con .git (inclusivo), o None si no hay repo."""
        start = path if path.is_dir() else path.parent
        current = start
        while True:
            if (current / ".git").exists():
                return current
            parent = current.parent
            if parent == current:
                return None  # raíz del filesystem: sin repo
            current = parent

    def _reminder_for_path(self, path: Path) -> str | None:
        root = self._repo_root(path)
        if root is None:
            return None
        # C4 desde el directorio tocado: recoge AGENTS.md anidados entre el
        # archivo y la raíz del repo (outermost first), sin global.
        start = path if path.is_dir() else path.parent
        instr = load_instructions(start, include_global=False)
        if not instr.found or instr.version in self._injected:
            return None
        self._injected.add(instr.version)
        return (
            "\n\n[system-reminder — REGLAS DEL REPO DETECTADAS] Tocaste archivos "
            f"dentro del repo {root}, fuera del directorio de trabajo inicial. "
            "Estas instrucciones del proyecto NO estaban en tu contexto al "
            "arrancar y siguen vigentes SIEMPRE:" + render_for_prompt(instr)
        )
