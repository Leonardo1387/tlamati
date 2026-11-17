"""C4 — Project instructions loader: AGENTS.md (+ CLAUDE.md compat).

AGENTS.md is the cross-agent de-facto standard (OpenAI codex, Cursor, Jules,
Factory...); Claude Code repos carry CLAUDE.md instead. Tlamati reads BOTH —
"best of the 8": a repo that already instructs another agent instructs this
one with zero changes.

Merge order (GUIA C4: repo→global→override; donor: codex merges
global→repo-root→nested-deepest): OUTERMOST first, deepest last, so the file
closest to the working directory can refine/override what's above it. The
merged block is injected into the cacheable prefix with a CONTENT HASH
version marker: the prefix only changes when the instructions change —
never per-run metadata (cache stability rule, research/05).

Collection walk: from cwd upward to the repo boundary (first ancestor with
.git, inclusive) or the filesystem root if no git repo. Per directory:
AGENTS.md wins; CLAUDE.md is used only when that directory has no AGENTS.md.
A global file (~/.config/tlamati/AGENTS.md) always goes first.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

PRIMARY_NAME = "AGENTS.md"
FALLBACK_NAME = "CLAUDE.md"  # Claude Code compat (same repo-level role)
GLOBAL_INSTRUCTIONS = Path(".config") / "tlamati" / "AGENTS.md"


@dataclass(frozen=True)
class Instructions:
    """Merged project instructions, ready for prefix injection."""

    sources: tuple[Path, ...]
    block: str  # "" when nothing was found
    version: str  # sha256[:12] of block — prefix versioning (GUIA C4)

    @property
    def found(self) -> bool:
        return bool(self.block)


def _collect_repo_files(cwd: Path) -> list[Path]:
    """Walk cwd → repo boundary (first .git ancestor, inclusive) or fs root.
    Returns per-dir instruction files, OUTERMOST first."""
    chain: list[Path] = []
    current = cwd.resolve()
    while True:
        primary = current / PRIMARY_NAME
        fallback = current / FALLBACK_NAME
        if primary.is_file():
            chain.append(primary)
        elif fallback.is_file():
            chain.append(fallback)
        if (current / ".git").exists():
            break  # repo boundary reached (inclusive)
        parent = current.parent
        if parent == current:
            break  # filesystem root
        current = parent
    chain.reverse()  # outermost first → deepest refines last
    return chain


def load_instructions(
    cwd: Path, *, global_path: Path | None = None, include_global: bool = True
) -> Instructions:
    """Merge global + repo-chain instruction files into one versioned block."""
    files: list[Path] = []
    if include_global:
        gp = global_path if global_path is not None else Path.home() / GLOBAL_INSTRUCTIONS
        if gp.is_file():
            files.append(gp)
    files.extend(_collect_repo_files(cwd))

    if not files:
        return Instructions(sources=(), block="", version="")

    parts: list[str] = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue  # unreadable file = skipped honestly, never fatal
        if content:
            parts.append(f"## {f}\n\n{content}")
    block = "\n\n".join(parts)
    if not block:
        return Instructions(sources=tuple(files), block="", version="")
    version = hashlib.sha256(block.encode("utf-8")).hexdigest()[:12]
    return Instructions(sources=tuple(files), block=block, version=version)


def render_for_prompt(instr: Instructions) -> str:
    """The exact text appended to the system prompt (stable per content)."""
    if not instr.found:
        return ""
    return (
        "\n\n# INSTRUCCIONES DEL PROYECTO (AGENTS.md/CLAUDE.md — siguen vigentes "
        f"siempre)\n<!-- instrucciones v:{instr.version} -->\n\n{instr.block}"
    )
