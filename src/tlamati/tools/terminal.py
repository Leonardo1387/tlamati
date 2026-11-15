"""B2 — terminal tool: foreground shell with timeout + honest truncation.

B3 will wrap ``cmd`` in a bwrap jail (sandboxable=True already declared).
Until then the command runs directly, pinned to workdir (same semantics as
Fase A — the A7 baseline depends on it). background+poll is v1.1 (GUIA §B2).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

TERMINAL_TIMEOUT_S = 120.0
MAX_OUTPUT_CHARS = 50_000


def make_terminal_tools(workdir: Path) -> list[Any]:
    from tlamati.tools.registry import Permission, Tool

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
        truncated = len(out) > MAX_OUTPUT_CHARS
        if truncated:
            out = out[:MAX_OUTPUT_CHARS] + "\n... [truncated]"
        return f"[exit {proc.returncode}]\n{out}".rstrip()

    return [
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
