"""C2 — Durable memory: MEMORY.md + USER.md with HARD CAPS.

Design (GUIA C2 destilada, sources inline):
- Two fixed files per scope, donor: Claude Code memory subsystem (research/05
  §2): MEMORY.md (durable facts/notes) + USER.md (who the user is).
- HARD CAPS (donor: CC events tengu_team_mem_sync_* + team_mem_entries_capped
  → entries are capped): max entries, max lines, max chars per file. When an
  add would overflow, it is REJECTED with honest stats so the agent must
  CONSOLIDATE (replace/remove) instead of accumulating — the same pressure
  model hermes uses.
- Scopes v1: ``user`` (~/.local/share/tlamati/memory/) + ``project``
  (<cwd>/.tlamati/memory/). CC has 4 scopes; the other 2 are v2 (GUIA C2).
- Entries are single-paragraph bullets separated by blank lines. An entry is
  identified for replace/remove by a unique substring (old_text), like the
  hermes memory tool the founder already knows.
- Seed rules (donor: CC Osmani ratchet, research/05 §1) are part of the file
  header, not entries: absolute paths, no recap, no emojis.

Files are the source of truth (plain markdown, user-editable, git-friendly).
No database: memory must survive tool migrations and be readable by a human.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Hard caps (donor: CC entries-capped sync events). Generous but finite:
# the goal is consolidation pressure, not a shoebox.
MAX_ENTRIES = 100
MAX_CHARS = 24_000
MAX_ENTRY_CHARS = 2_000

HEADER_MEMORY = (
    "# MEMORY — hechos durables del proyecto (límites: "
    f"{MAX_ENTRIES} entradas / {MAX_CHARS} chars)\n"
    "<!-- Reglas (semilla Osmani, research/05): rutas absolutas, sin "
    "recapitulación, sin emojis. Si está lleno: consolida (replace/remove) "
    "en el mismo batch. Guarda hechos NUEVOS y durables (nombres de proyecto, "
    "decisiones, constraints) cuando aparezcan — NO guardes progreso de tarea "
    "ni nada que caduque en días. Escríbelos declarativos ('el proyecto X usa "
    "Y'), nunca imperativos. -->\n"
)
HEADER_USER = (
    "# USER — quién es el usuario (límites: "
    f"{MAX_ENTRIES} entradas / {MAX_CHARS} chars)\n"
    "<!-- Preferencias, correcciones, estilo. Cuando el usuario corrija o "
    "declare una preferencia, guárdala aquí en el mismo turno. Consolidar al "
    "llenarse. -->\n"
)

ENTRY_SEP = "\n\n"


@dataclass(frozen=True)
class MemoryStats:
    entries: int
    chars: int
    max_entries: int = MAX_ENTRIES
    max_chars: int = MAX_CHARS

    def human(self) -> str:
        return f"{self.entries}/{self.max_entries} entradas, {self.chars}/{self.max_chars} chars"


@dataclass(frozen=True)
class MemoryFile:
    """One parsed memory file: header + entries."""

    path: Path
    header: str
    entries: tuple[str, ...]

    @property
    def stats(self) -> MemoryStats:
        body = ENTRY_SEP.join(self.entries)
        return MemoryStats(entries=len(self.entries), chars=len(body))

    def render(self) -> str:
        if not self.entries:
            return self.header
        return self.header + "\n" + ENTRY_SEP.join(self.entries) + "\n"


class MemoryError(ValueError):
    """Honest rejection (cap overflow, entry not found, ambiguous old_text)."""


def _parse(path: Path, default_header: str) -> MemoryFile:
    if not path.is_file():
        return MemoryFile(path=path, header=default_header, entries=())
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header_lines: list[str] = []
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# ") or line.startswith("<!--") or (not line.strip() and i == 0):
            header_lines.append(line)
            body_start = i + 1
        else:
            break
    header = "\n".join(header_lines) if header_lines else default_header
    body = "\n".join(lines[body_start:]).strip()
    entries = tuple(e.strip() for e in body.split(ENTRY_SEP) if e.strip()) if body else ()
    return MemoryFile(path=path, header=header, entries=entries)


class MemoryStore:
    """Two files per scope, cap-enforced, atomic batches."""

    def __init__(self, dir_path: str | Path) -> None:
        self.dir = Path(dir_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.memory_path = self.dir / "MEMORY.md"
        self.user_path = self.dir / "USER.md"

    def load(self, target: str) -> MemoryFile:
        if target == "memory":
            return _parse(self.memory_path, HEADER_MEMORY)
        if target == "user":
            return _parse(self.user_path, HEADER_USER)
        raise MemoryError(f"target inválido: {target!r} (usa 'memory' o 'user')")

    def _write(self, mf: MemoryFile) -> None:
        tmp = mf.path.with_suffix(".md.tmp")
        tmp.write_text(mf.render(), encoding="utf-8")
        tmp.replace(mf.path)  # atomic on POSIX

    def apply_batch(self, target: str, operations: list[dict[str, str]]) -> MemoryStats:
        """Apply add/replace/remove ATOMICALLY: validate everything against the
        projected state, then write once. Any failure → MemoryError, file
        untouched (donor: hermes memory batch semantics the founder knows)."""
        if not operations:
            raise MemoryError("batch vacío")
        mf = self.load(target)
        entries = list(mf.entries)
        for i, op in enumerate(operations):
            action = op.get("action", "")
            content = (op.get("content") or "").strip()
            old_text = (op.get("old_text") or "").strip()
            if action == "add":
                if not content:
                    raise MemoryError(f"op[{i}]: add sin content")
                if len(content) > MAX_ENTRY_CHARS:
                    raise MemoryError(
                        f"op[{i}]: entrada demasiado larga ({len(content)} > {MAX_ENTRY_CHARS})"
                    )
                entries.append(content)
            elif action in ("replace", "remove"):
                if not old_text:
                    raise MemoryError(f"op[{i}]: {action} sin old_text")
                matches = [j for j, e in enumerate(entries) if old_text in e]
                if not matches:
                    raise MemoryError(f"op[{i}]: old_text no encontrado: {old_text[:60]!r}")
                if len(matches) > 1:
                    raise MemoryError(
                        f"op[{i}]: old_text ambiguo ({len(matches)} entradas); sé más específico"
                    )
                if action == "replace":
                    if not content:
                        raise MemoryError(f"op[{i}]: replace sin content")
                    if len(content) > MAX_ENTRY_CHARS:
                        raise MemoryError(f"op[{i}]: entrada demasiado larga")
                    entries[matches[0]] = content
                else:
                    del entries[matches[0]]
            else:
                raise MemoryError(f"op[{i}]: acción inválida {action!r} (add|replace|remove)")

        # Caps are checked on the FINAL projected state (batch can free room
        # and add in one call — the whole point of atomic consolidation).
        body_chars = len(ENTRY_SEP.join(entries))
        if len(entries) > MAX_ENTRIES:
            raise MemoryError(
                f"el batch deja {len(entries)} entradas (máx {MAX_ENTRIES}); "
                "consolida con replace/remove"
            )
        if body_chars > MAX_CHARS:
            raise MemoryError(f"el batch deja {body_chars} chars (máx {MAX_CHARS}); consolida")
        new_mf = MemoryFile(path=mf.path, header=mf.header, entries=tuple(entries))
        self._write(new_mf)
        return new_mf.stats

    def render_for_prompt(self) -> str:
        """Both files as ONE stable text block for the cacheable prefix.

        Prefix stability (donor: CC attribution-header trick, research/05):
        the block changes ONLY when memory changes — never per-turn metadata.
        """
        parts: list[str] = []
        for target in ("memory", "user"):
            mf = self.load(target)
            if mf.entries:
                parts.append(mf.render().rstrip())
        return "\n\n".join(parts)

    def touch_marker(self) -> str:
        """Content hash-lite for prefix versioning (C4 will use the same idea)."""
        rendered = self.render_for_prompt()
        return f"{len(rendered)}-{sum(ord(c) for c in rendered[:200])}"


def default_memory_dir() -> Path:
    return Path.home() / ".local" / "share" / "tlamati" / "memory"


def project_memory_dir(cwd: Path) -> Path:
    return cwd / ".tlamati" / "memory"


def seed_if_empty(store: MemoryStore) -> None:
    """Create the two files with their headers if absent (first run)."""
    for target, header in (("memory", HEADER_MEMORY), ("user", HEADER_USER)):
        mf = store.load(target)
        if not mf.path.is_file():
            store._write(MemoryFile(path=mf.path, header=header, entries=()))
