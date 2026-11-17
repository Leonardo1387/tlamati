"""C3 — Skills: SKILL.md discovery + `skill_view` tool.

Format is 100% hermes-compatible BY DESIGN (GUIA C3 destilada): a skill is a
directory with a SKILL.md whose YAML frontmatter carries `name` + `description`
and whose body is markdown. Linked files live in references/, templates/,
scripts/, assets/ subdirs.

The migration promise (founder's "1-click" differentiator): pointing
``SkillLibrary`` at ~/.hermes/skills reads an existing hermes library as-is —
no conversion, no re-export. Tlamati skills dirs default to
~/.local/share/tlamati/skills (user) + .tlamati/skills (project), and extra
dirs can be added by config/flag (that's how hermes compat ships: one flag).

Injection model (donor: hermes skills_list/skill_view split; CC activate-skill
+ gemini skills/ scanning): the system prompt carries ONLY the catalog
(name + description, stable order = cacheable prefix intact). Full bodies are
loaded ON DEMAND through the `skill_view` tool — a skill body never bloats the
prefix until the model decides it needs it. skill_view output is
microcompact-whitelisted: re-fetchable from disk at zero cost.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tlamati.tools.registry import Tool

MAX_BODY_CHARS = 100_000  # honest truncation at the spout (M1 rule)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path  # SKILL.md
    category: str = ""

    @property
    def dir(self) -> Path:
        return self.path.parent

    def linked_files(self) -> dict[str, list[str]]:
        """references/templates/scripts/assets inventories (relative paths)."""
        out: dict[str, list[str]] = {}
        for sub in ("references", "templates", "scripts", "assets"):
            d = self.dir / sub
            if d.is_dir():
                files = sorted(str(p.relative_to(self.dir)) for p in d.rglob("*") if p.is_file())
                if files:
                    out[sub] = files
        return out


def parse_skill(skill_md: Path, category: str = "") -> Skill | None:
    """Parse frontmatter; None if missing/invalid (skip honestly, never crash
    the catalog — a broken skill file must not brick the agent)."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    name = str(fm.get("name", "")).strip()
    desc = str(fm.get("description", "")).strip()
    if not name or not desc:
        return None
    return Skill(name=name, description=desc, path=skill_md, category=category)


class SkillLibrary:
    """Scans skill roots (stable order), dedupes by name (first root wins)."""

    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots
        self._skills: dict[str, Skill] = {}
        self.rescan()

    def rescan(self) -> None:
        skills: dict[str, Skill] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for skill_md in sorted(root.glob("*/SKILL.md")) + sorted(root.glob("*/*/SKILL.md")):
                # hidden dirs (.archive/ in hermes = retired skills) are skipped
                rel = skill_md.parent.relative_to(root)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                category = str(rel.parent) if len(rel.parts) > 1 else ""
                sk = parse_skill(skill_md, category=category)
                if sk is not None and sk.name not in skills:
                    skills[sk.name] = sk
        self._skills = skills

    def catalog(self) -> list[Skill]:
        return sorted(self._skills.values(), key=lambda s: (s.category, s.name))

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def catalog_text(self, only: Collection[str] | None = None) -> str:
        """The block injected into the system prompt. Stable order → the
        cacheable prefix only changes when the library changes. `only` (C6
        routing): restrict to a name allowlist — callers must pass a STABLE
        allowlist per run (workspace-level), never per turn (cache sacred)."""
        lines = [
            "Skills disponibles (procedimientos reutilizables). Para usar una:",
            "skill_view(name). Solo carga las relevantes para la tarea actual.",
        ]
        allowed = {n.lower() for n in only} if only is not None else None
        for s in self.catalog():
            if allowed is not None and s.name.lower() not in allowed:
                continue
            prefix = f"{s.category}/" if s.category else ""
            lines.append(f"- {prefix}{s.name}: {s.description}")
        return "\n".join(lines)


def make_skill_tools(library: SkillLibrary) -> list[Tool]:
    async def skill_list_run(args: dict[str, Any]) -> str:
        cat = library.catalog()
        if not cat:
            return "(sin skills instaladas)"
        return library.catalog_text() + f"\n\n({len(cat)} skills)"

    async def skill_view_run(args: dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        sk = library.get(name)
        if sk is None:
            known = ", ".join(s.name for s in library.catalog()[:20])
            return f"ERROR: skill {name!r} no existe. Disponibles: {known}"
        file_path = str(args.get("file_path", "")).strip()
        if file_path:
            target = (sk.dir / file_path).resolve()
            # Path-escape guard: linked files only, inside the skill dir.
            if not str(target).startswith(str(sk.dir.resolve())):
                return "ERROR: file_path fuera del directorio del skill"
            if not target.is_file():
                return f"ERROR: {file_path} no existe en {sk.name}"
            return target.read_text(encoding="utf-8", errors="replace")[:MAX_BODY_CHARS]
        body = sk.path.read_text(encoding="utf-8", errors="replace")
        out = body[:MAX_BODY_CHARS]
        if len(body) > MAX_BODY_CHARS:
            out += "\n... [truncated]"
        linked = sk.linked_files()
        if linked:
            out += "\n\nLinked files (skill_view con file_path para leerlos):"
            for files in linked.values():
                for f in files:
                    out += f"\n- {f}"
        return out

    return [
        Tool(
            name="skill_view",
            description=(
                "Cargar el contenido completo de una skill (SKILL.md) o un archivo "
                "vinculado (file_path: references/…, templates/…, scripts/…). "
                "Resultado re-obtenible del disco."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "file_path": {
                        "type": "string",
                        "description": "opcional: archivo vinculado dentro del skill",
                    },
                },
                "required": ["name"],
            },
            run=skill_view_run,
        ),
        Tool(
            name="skill_list",
            description="Listar skills instaladas (nombre + descripción).",
            input_schema={"type": "object", "properties": {}},
            run=skill_list_run,
        ),
    ]


def default_skill_roots(cwd: Path, extra: list[Path] | None = None) -> list[Path]:
    """Project first (overrides), then user, then any extra dirs (e.g. the
    hermes library — the 1-flag migration)."""
    roots = [
        cwd / ".tlamati" / "skills",
        Path.home() / ".local" / "share" / "tlamati" / "skills",
    ]
    if extra:
        roots.extend(extra)
    return roots
