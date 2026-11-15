"""Built-in tools (migrated from tools_min/, now formal ``Tool`` instances).

B1 migration keeps behaviour byte-identical (the A7 baseline is the ratchet:
5/5 tasks, same tool semantics). B2 replaces these bodies with the formal
versions (read with truncation metadata, fuzzy edit, rg search, sandboxed
terminal). Permission defaults stay AUTO until B4 wires policy config;
``terminal`` is marked sandboxable so B3 (bwrap) can jail it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tlamati.tools.registry import Permission, Tool, truncate

TERMINAL_TIMEOUT_S = 120.0


def _resolve(workdir: Path, path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = workdir / p
    return p.resolve()


def make_tools(workdir: Path) -> list[Tool]:
    """Build the built-in toolset pinned to ``workdir``."""

    async def read_file(args: dict[str, Any]) -> str:
        path = _resolve(workdir, str(args.get("path", "")))
        if not path.is_file():
            return f"ERROR: no such file: {path}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"ERROR: {e}"
        numbered = "\n".join(f"{i + 1}|{line}" for i, line in enumerate(text.splitlines()))
        out, _ = truncate(numbered)
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
        out, _ = truncate(out)
        return f"[exit {proc.returncode}]\n{out}".rstrip()

    return [
        Tool(
            name="read_file",
            description="Read a text file with line numbers (relative to the working directory).",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "file path"}},
                "required": ["path"],
            },
            run=read_file,
            permission=Permission.AUTO,
            sandboxable=False,
        ),
        Tool(
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
            permission=Permission.AUTO,
            sandboxable=False,
        ),
        Tool(
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
            permission=Permission.AUTO,
            sandboxable=True,  # B3: bwrap jail target
        ),
    ]
