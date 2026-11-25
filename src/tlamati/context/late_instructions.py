"""NIVEL 1a — inyección tardía de instrucciones de repo (dogfood #6).

Causa raíz del dogfood #6: la sesión arrancó desde ~ (home), el cargador C4
camina del cwd al primer ancestro .git y no encontró nada — las reglas del
repo (AGENTS.md de proyecto-legal) NUNCA llegaron al contexto del agente.

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
import subprocess
from pathlib import Path
from typing import Any

from tlamati.context.instructions import load_instructions, render_for_prompt

# Tools que "tocan" archivos según el handoff (edit/write_file/terminal cd).
# El conocimiento de qué tools cuentan vive AQUÍ, no en el Registry.
_TOUCH_TOOLS = frozenset({"write_file", "edit", "terminal"})

# Heurística honesta de ``cd <path>`` en comandos shell (POSIX + bash):
# no parseamos shell completo — extraemos los destinos de cd y los probamos.
_CD_RE = re.compile(r"\bcd\s+(--[^\s;&|]+\s+)*([^\s;&|()]+)")

# NIVEL 2f: advisory pre-commit — comandos git que preparan/ejecutan commit.
_GIT_STAGE_RE = re.compile(r"\bgit\s+(?:add|commit)\b")

# Marcadores con los que un AGENTS.md señala archivos compartidos/críticos.
_CRITICAL_MARKERS = ("compartido", "crítico", "critico")

# Token de ruta dentro de una línea marcada: dir con /, palabra suelta con
# slash final, o nombre de archivo con extensión.
_PATH_TOKEN_RE = re.compile(r"[\w.\-]+(?:/[\w.\-*]+)*/?")
_FILE_EXT_RE = re.compile(r"[\w\-]+\.\w+")

_GIT_TIMEOUT_S = 5.0


def critical_paths_from_instructions(text: str) -> set[str]:
    """Rutas que el AGENTS.md marca como compartidas/críticas.

    Heurística honesta y sin LLM: líneas que contienen "compartido"/
    "crítico" aportan sus tokens con apariencia de ruta (contienen "/",
    terminan en "/" — directorios — o tienen extensión de archivo).
    Nunca inventa: si el repo no marca nada, devuelve vacío (silencio
    total, advisory)."""
    out: set[str] = set()
    for line in text.splitlines():
        low = line.lower()
        if any(m in low for m in _CRITICAL_MARKERS):
            for tok in _PATH_TOKEN_RE.findall(line):
                raw = tok.strip("`*\"'")
                is_dir = raw.endswith("/")
                t = raw.rstrip("/")
                if not t:
                    continue
                if is_dir or "/" in t or _FILE_EXT_RE.fullmatch(t):
                    out.add(t)
    return out


def _git_staged_files(root: Path) -> list[str]:
    """Archivos en el índice de git (diff --cached). Falla → lista vacía
    (advisory nunca rompe la corrida)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


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

        Dos piezas (se concatenan si ambas aplican):
        - NIVEL 1a: reglas del repo detectado al tocar un path fuera del cwd.
        - NIVEL 2f: advisory pre-commit en git add/commit — si el índice toca
          archivos que el AGENTS.md del repo marca como compartido/crítico,
          recordatorio de no-regresión. Advisory: MENSAJE, nunca bloqueo.
        """
        if tool_name not in _TOUCH_TOOLS:
            return None
        try:
            parts: list[str] = []
            if tool_name == "terminal":
                advisory = self._commit_advisory(str(args.get("command", "")))
                if advisory:
                    parts.append(advisory)
            paths = self._touched_paths(tool_name, args)
            for p in paths:
                text = self._reminder_for_path(p)
                if text is not None:
                    parts.append(text)
                    break  # una inyección 1a por tool call es suficiente
            return "\n".join(parts) if parts else None
        except Exception:
            return None  # advisory: jamás romper el loop por un recordatorio

    # ------------------------------------------------------------- interno
    def _commit_advisory(self, command: str) -> str | None:
        """NIVEL 2f: advisory de no-regresión tras git add/commit.

        Si el diff staged toca archivos que el AGENTS.md del repo marca como
        compartido/crítico, recordárselo al agente (MENSAJE, nunca bloqueo —
        filosofía M8: advisory no muta el comportamiento del tool)."""
        if not _GIT_STAGE_RE.search(command):
            return None
        root = self._repo_root(self.workdir)
        for p in self._touched_paths("terminal", {"command": command}):
            root = self._repo_root(p) or root
        if root is None:
            return None
        instr = load_instructions(root, include_global=False)
        if not instr.found:
            return None
        critical = critical_paths_from_instructions(instr.block)
        if not critical:
            return None
        staged = _git_staged_files(root)
        hits = sorted({f for f in staged for c in critical if f == c or f.startswith(c + "/")})
        if not hits:
            return None
        return (
            "\n\n[system-reminder — ADVISORY PRE-COMMIT] El índice de git toca "
            f"archivo(s) marcado(s) como compartido/crítico por el AGENTS.md "
            f"del repo: {', '.join(hits)}. Antes de commitear verifica que no "
            "regresas reglas del proyecto (advisory: esto NO bloquea el "
            "commit)."
        )

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
