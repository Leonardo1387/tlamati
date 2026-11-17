"""C6 — Workspaces + routing.md: declarative context routing (PRD F6b).

Donor: research/03 §1 ("agents as folders"): the workspace file is the
operating system of the agent — folders + markdown + natural-language
routing, NO database, NO magic RAG. Three layers, which are CACHE
BOUNDARIES (research/03 lesson #4):

- Layer 1 MAPA: `.tlamati/routing.md` at the project root — a parseable
  markdown table (task pattern → workspace → what to load / omit / which
  skills to wire just-in-time). Stable → part of the cacheable prefix,
  versioned by content hash (same pattern as C4 instructions).
- Layer 2 HABITACIONES: per-workspace context file, semi-stable. Injected
  into the prefix ONLY for the ACTIVE workspace (never all of them).
- Layer 3 MESAS: the real files. NEVER in the prefix — the model reads them
  on demand with read_file (naming convention as index, lesson #2).

Settled decisions (founder, 17-nov):
1. Format = parseable markdown table (deterministic), not free-form prose.
2. Scope = project only (`.tlamati/routing.md`); no global user-level file
   in v1 (KISS — merge rules for a case that doesn't exist yet).
3. Task→workspace match = harness-side fnmatch globs (deterministic), NOT a
   model tool. `--workspace NAME` forces; first matching row wins.

Fail-soft contract: a missing/broken/unreadable routing.md degrades
honestly (empty Routing, no prefix change, warning via `error`) and NEVER
breaks the run. Without routing.md the prefix is byte-identical to pre-C6
(cache sacred — baseline ratchet).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

ROUTING_DIR = ".tlamati"
ROUTING_FILE = "routing.md"

# Header aliases (normalized: lowercase, accents stripped) → canonical field.
_HEADER_ALIASES: dict[str, str] = {
    "workspace": "workspace",
    "zona": "workspace",
    "patron": "pattern",
    "tarea": "pattern",
    "contexto": "context_file",
    "cargar": "load",
    "omitir": "omit",
    "skills": "skills",
}
_REQUIRED_HEADERS = {"workspace", "pattern"}


def _normalize_header(cell: str) -> str:
    norm = cell.strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        norm = norm.replace(a, b)
    return norm


def _split_list(cell: str) -> tuple[str, ...]:
    """Cells hold comma/semicolon separated items; empty cell = empty tuple."""
    items = [p.strip() for p in cell.replace(";", ",").split(",")]
    return tuple(p for p in items if p)


@dataclass(frozen=True)
class Workspace:
    """One row of routing.md = one 'room' (layer 2)."""

    name: str
    pattern: str  # fnmatch glob matched against the task text
    context_file: str = ""  # relative to project root; injected when active
    load: tuple[str, ...] = ()  # guidance: files the model should read_file
    omit: tuple[str, ...] = ()  # guidance: paths to ignore
    skills: tuple[str, ...] = ()  # just-in-time skill allowlist (stable per run)


@dataclass(frozen=True)
class Routing:
    """Parsed routing.md + resolved active workspace, ready for the prefix."""

    source: Path | None
    project_root: Path | None
    workspaces: tuple[Workspace, ...]
    active: Workspace | None
    table: str  # raw table lines of layer 1 MAPA (verbatim into the prefix)
    context_block: str  # layer-2 text of the ACTIVE workspace ("" if none)
    version: str  # sha256[:12] of table+active context — prefix versioning
    error: str = ""  # honest degradation note (never fatal)

    @property
    def found(self) -> bool:
        return bool(self.workspaces)


def _find_routing_file(cwd: Path) -> tuple[Path, Path] | None:
    """Walk cwd → repo boundary (first .git ancestor, inclusive) or fs root,
    looking for <dir>/.tlamati/routing.md. Same frontier rule as C4."""
    current = cwd.resolve()
    while True:
        candidate = current / ROUTING_DIR / ROUTING_FILE
        if candidate.is_file():
            return candidate, current
        if (current / ".git").exists():
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def parse_routing_table(text: str) -> tuple[Workspace, ...]:
    """Parse the FIRST markdown table with workspace+patrón headers.

    Rows with a missing required cell are skipped honestly (never crash the
    load). Non-table lines (prose, headings) are ignored — the human can
    annotate the file freely around the table."""
    rows: list[Workspace] = []
    columns: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            if columns is not None:
                break  # table ended
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} and c for c in cells):
            continue  # separator row (|---|---|)
        if columns is None:
            normalized = [_normalize_header(c) for c in cells]
            mapped = [_HEADER_ALIASES.get(n, "") for n in normalized]
            if not _REQUIRED_HEADERS.issubset(set(mapped)):
                continue  # not the routing table header — keep looking
            columns = mapped
            continue
        if len(cells) != len(columns):
            continue  # malformed row → skipped honestly
        data = {col: cell for col, cell in zip(columns, cells, strict=True) if col}
        name = data.get("workspace", "").strip()
        pattern = data.get("pattern", "").strip()
        if not name or not pattern:
            continue
        rows.append(
            Workspace(
                name=name,
                pattern=pattern,
                context_file=data.get("context_file", "").strip(),
                load=_split_list(data.get("load", "")),
                omit=_split_list(data.get("omit", "")),
                skills=_split_list(data.get("skills", "")),
            )
        )
    return tuple(rows)


def resolve_workspace(
    workspaces: tuple[Workspace, ...], *, task: str = "", forced: str = ""
) -> tuple[Workspace | None, str]:
    """Deterministic resolution: flag > first fnmatch of the task text > None.

    Returns (workspace, error). An unknown --workspace name is an honest
    error note (run continues, map still injected) — never fatal."""
    if forced:
        for ws in workspaces:
            if ws.name.lower() == forced.strip().lower():
                return ws, ""
        known = ", ".join(w.name for w in workspaces)
        return None, f"workspace forzado {forced!r} no existe en routing.md (disponibles: {known})"
    if task:
        low = task.lower()
        for ws in workspaces:  # first match wins (row order = priority)
            if fnmatch(low, ws.pattern.lower()):
                return ws, ""
    return None, ""


def load_routing(cwd: Path, *, task: str = "", workspace: str = "") -> Routing:
    """Load .tlamati/routing.md, resolve the active workspace, build the
    layer-2 context block. Any problem = honest empty/partial Routing."""
    found = _find_routing_file(cwd)
    if found is None:
        return Routing(
            source=None,
            project_root=None,
            workspaces=(),
            active=None,
            table="",
            context_block="",
            version="",
        )
    source, project_root = found
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as e:
        return Routing(
            source=source,
            project_root=project_root,
            workspaces=(),
            active=None,
            table="",
            context_block="",
            version="",
            error=f"routing.md no legible ({e})",
        )
    workspaces = parse_routing_table(text)
    if not workspaces:
        return Routing(
            source=source,
            project_root=project_root,
            workspaces=(),
            active=None,
            table="",
            context_block="",
            version="",
            error=f"{source} no contiene una tabla de routing válida "
            "(se esperan cabeceras 'workspace' y 'patrón')",
        )
    active, err = resolve_workspace(workspaces, task=task, forced=workspace)

    context_block = ""
    if active is not None and active.context_file:
        ctx_path = (project_root / active.context_file).resolve()
        try:
            # path-escape guard: the context file must live inside the project
            ctx_path.relative_to(project_root.resolve())
            in_project = True
        except ValueError:
            in_project = False
        if not in_project:
            err = (err + "; " if err else "") + (
                f"contexto {active.context_file!r} está fuera del proyecto — omitido"
            )
        else:
            try:
                context_block = ctx_path.read_text(encoding="utf-8").strip()
            except OSError:
                context_block = ""
                err = (err + "; " if err else "") + (
                    f"contexto {active.context_file!r} no legible — omitido"
                )

    table_block = _table_block(text)
    digest_src = table_block + "\x00" + (active.name if active else "") + "\x00" + context_block
    version = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:12]
    return Routing(
        source=source,
        project_root=project_root,
        workspaces=workspaces,
        active=active,
        table=table_block,
        context_block=context_block,
        version=version,
        error=err,
    )


def _table_block(text: str) -> str:
    """The raw table lines (layer 1 MAPA) — what goes verbatim into the prefix."""
    lines: list[str] = []
    in_table = False
    for raw in text.splitlines():
        if raw.strip().startswith("|"):
            in_table = True
            lines.append(raw.rstrip())
        elif in_table:
            break
    return "\n".join(lines)


def render_for_prompt(routing: Routing) -> str:
    """The exact text appended to the prefix AFTER instructions (C4).

    Empty string when there is no routing table → prefix byte-identical to
    pre-C6 (cache sacred). The MAPA (full table) is always injected (layer 1,
    stable); layer-2 context ONLY for the active workspace."""
    if not routing.found:
        return ""
    parts = [
        "\n\n# ROUTING (workspaces — mapa del proyecto)",
        f"<!-- routing v:{routing.version} -->",
        "",
        "Mapa completo (capa 1):",
        routing.table,
    ]
    if routing.active is not None:
        ws = routing.active
        parts.append(f"\nWorkspace ACTIVO: {ws.name} (patrón {ws.pattern!r}).")
        if ws.load:
            parts.append("Lee con read_file (capa 3): " + ", ".join(ws.load))
        if ws.omit:
            parts.append("OMITE (no cargar): " + ", ".join(ws.omit))
        if ws.skills:
            parts.append("Skills cableadas a este workspace: " + ", ".join(ws.skills))
        if routing.context_block:
            parts.append(f"\nContexto del workspace (capa 2):\n{routing.context_block}")
    else:
        parts.append(
            "\nNingún workspace activo: usa el mapa para decidir qué leer (read_file) y qué omitir."
        )
    return "\n".join(parts)
