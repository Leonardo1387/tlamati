"""PROVISIONAL minimal toolset for Fase A (corrección aprobada 14-nov).

Han-Lee test: these are TEMPORAL — a formal registry (name, schema,
permission, sandbox_policy) replaces them in B1-B3. No sandbox here; the
terminal runs foreground with a timeout and the working directory is pinned.

Kept deliberately tiny: 3 tools, ~150 LOC, one dispatch dict.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tlamati.core.messages import ToolResult
from tlamati.providers.base import ToolSpec

MAX_OUTPUT_CHARS = 50_000  # M1: truncate at the spout, honest marker
TERMINAL_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class MiniTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[[dict[str, Any]], Awaitable[str]]

    def as_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, input_schema=self.input_schema
        )


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n... [truncated]", True


def _resolve(workdir: Path, path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = workdir / p
    return p.resolve()


def make_tools(workdir: Path) -> list[MiniTool]:
    """Build the provisional toolset pinned to ``workdir``."""

    async def read_file(args: dict[str, Any]) -> str:
        path = _resolve(workdir, str(args.get("path", "")))
        if not path.is_file():
            return f"ERROR: no such file: {path}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"ERROR: {e}"
        numbered = "\n".join(f"{i + 1}|{line}" for i, line in enumerate(text.splitlines()))
        out, _ = _truncate(numbered)
        return out

    async def write_file(args: dict[str, Any]) -> str:
        path = _resolve(workdir, str(args.get("path", "")))
        content = str(args.get("content", ""))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"ERROR: {e}"
        return f"wrote {len(content)} chars to {path}"

    async def terminal(args: dict[str, Any]) -> str:
        cmd = str(args.get("command", ""))
        if not cmd:
            return "ERROR: empty command"
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TERMINAL_TIMEOUT_S)
        except TimeoutError:
            if proc is not None:
                proc.kill()
            return f"ERROR: command timed out after {TERMINAL_TIMEOUT_S:.0f}s"
        except OSError as e:
            return f"ERROR: {e}"
        if proc is None or proc.returncode is None:
            return "ERROR: process did not complete"
        out = stdout.decode("utf-8", errors="replace")
        out, _ = _truncate(out)
        return f"[exit {proc.returncode}]\n{out}".rstrip()

    return [
        MiniTool(
            name="read_file",
            description="Read a text file with line numbers (relative to the working directory).",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "file path"}},
                "required": ["path"],
            },
            run=read_file,
        ),
        MiniTool(
            name="write_file",
            description="Write (create or fully overwrite) a text file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            run=write_file,
        ),
        MiniTool(
            name="terminal",
            description=(
                "Run a shell command in the working directory "
                f"(foreground, {TERMINAL_TIMEOUT_S:.0f}s timeout)."
            ),
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
            run=terminal,
        ),
    ]


async def execute(tool: MiniTool, raw_args: dict[str, Any], tool_call_id: str) -> ToolResult:
    """Run one tool, converting ANY failure into an honest ToolResult
    (is_error=True) — the loop never crashes on a tool bug."""
    try:
        content = await tool.run(raw_args)
        is_error = content.startswith("ERROR:")
    except Exception as e:
        content = f"ERROR: tool {tool.name} raised {type(e).__name__}: {e}"
        is_error = True
    content, truncated = _truncate(content)
    return ToolResult(
        tool_call_id=tool_call_id, content=content, is_error=is_error, truncated=truncated
    )
