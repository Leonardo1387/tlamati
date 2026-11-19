"""B2/B3 — terminal tool: foreground shell con timeout + truncado honesto.

B3: el comando corre DENTRO de la jaula bwrap (fs read-only + workdir rw +
sin red) cuando ``sandbox=True`` (default: ON si bwrap existe). Si bwrap no
está instalado hay degradación HONESTA: el comando corre sin jaula y el
resultado del tool lleva una nota visible. background+poll es v1.1 (GUIA §B2).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tlamati.sandbox.bwrap import SandboxProfile, bwrap_available, wrap_command

TERMINAL_TIMEOUT_S = 120.0
MAX_OUTPUT_CHARS = 50_000

_NO_SANDBOX_NOTE = "[sin sandbox: bwrap no está instalado — el comando corrió SIN jaula]\n"


def make_terminal_tools(
    workdir: Path, *, sandbox: bool | None = None, sandbox_net: bool = False
) -> list[Any]:
    """sandbox=None (default) → ON si bwrap existe; True/False → forzado.

    sandbox_net=True → --share-net dentro de la jaula (permiso separado,
    GUIA §B3; default OFF).
    """
    from tlamati.tools.registry import Permission, Tool

    if sandbox is None:
        sandbox = bwrap_available()
    profile = SandboxProfile(workdir=workdir, net=sandbox_net)

    async def terminal(args: dict[str, Any]) -> str:
        from tlamati.tools.winpath import normalize_win_in_command

        cmd = normalize_win_in_command(str(args.get("command", "")))
        effective = cmd
        no_jail = False
        if sandbox:
            wrapped = wrap_command(cmd, profile)
            if wrapped is None:
                # pedido ON pero bwrap desapareció en runtime → honesto, no yolo
                no_jail = True
            else:
                effective = wrapped
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_shell(
                effective,
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
        prefix = _NO_SANDBOX_NOTE if no_jail else ""
        return f"{prefix}[exit {proc.returncode}]\n{out}".rstrip()

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
            sandboxable=True,
            # B4 trifecta: si el comando PUDO tocar la red (red permitida o
            # sin jaula), su output cruzó la frontera → untrusted. Enjaulado
            # con red OFF no produce untrusted (la red es inalcanzable).
            produces_untrusted=bool(sandbox_net or not sandbox),
        ),
    ]
