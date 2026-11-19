"""B2 — search_files: ripgrep subprocess (rg 14.x installed 15-nov).

Modes:
- content: regex inside files (--json for structured parsing; capped results).
- files: glob by name (rg --files | fnmatch-style via rg -g).

Honest degradation: rg missing → ERROR telling the model why (never a silent
empty result that looks like "no matches"). Exit code 1 = no matches (NOT an
error). Exit 2 = real rg error (bad regex etc.) → surfaced verbatim.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

MAX_RESULTS = 50
RG_TIMEOUT_S = 30.0


def make_search_tools(workdir: Path) -> list[Any]:
    from tlamati.tools.registry import Permission, Tool

    async def search_files(args: dict[str, Any]) -> str:
        from tlamati.tools.winpath import WinPathError

        pattern = str(args.get("pattern", ""))
        target = str(args.get("target", "content"))
        path_arg = str(args.get("path", "."))
        try:
            base = _resolve(workdir, path_arg)
        except WinPathError as e:
            return f"ERROR: {e}"
        if not base.exists():
            return f"ERROR: path does not exist: {base}"

        rg = shutil.which("rg")
        if rg is None:
            return "ERROR: ripgrep (rg) is not installed on this machine"

        file_glob = args.get("file_glob")
        limit = min(int(args.get("limit", MAX_RESULTS)), 200)

        if target == "files":
            cmd = [rg, "--files", str(base)]
            if file_glob:
                cmd = [rg, "--files", "-g", str(file_glob), str(base)]
        else:
            cmd = [rg, "--json", "--max-count", str(limit), "--", pattern, str(base)]
            if file_glob:
                cmd = [
                    rg,
                    "--json",
                    "-g",
                    str(file_glob),
                    "--max-count",
                    str(limit),
                    "--",
                    pattern,
                    str(base),
                ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=RG_TIMEOUT_S)
        except TimeoutError:
            return f"ERROR: search timed out after {RG_TIMEOUT_S:.0f}s"
        except OSError as e:
            return f"ERROR: {e}"

        rc = proc.returncode if proc.returncode is not None else -1
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace").strip()

        if target == "files":
            if rc == 1:
                return "(no files found)"
            if rc != 0:
                return f"ERROR: rg exit {rc}: {err}"
            files = out.splitlines()[:limit]
            more = f"\n... [capped at {limit}]" if len(out.splitlines()) > limit else ""
            return "\n".join(files) + more

        # content mode: parse rg --json events
        if rc == 1:
            return "(no matches)"
        if rc != 0:
            return f"ERROR: rg exit {rc}: {err}"
        lines: list[str] = []
        count = 0
        for raw_line in out.splitlines():
            if count >= limit:
                lines.append(f"... [capped at {limit} matches]")
                break
            try:
                ev = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "match":
                continue
            d = ev["data"]
            path = d["path"].get("text", "?")
            ln = d.get("line_number", 0)
            text = d["lines"].get("text", "").rstrip("\n")
            lines.append(f"{path}:{ln}|{text}")
            count += 1
        return "\n".join(lines) if lines else "(no matches)"

    return [
        Tool(
            name="search_files",
            description=(
                "Search with ripgrep. target='content': regex inside files "
                "(returns path:line|text). target='files': find files by name "
                "glob (file_glob, e.g. '*.py'). Optional path (dir) and limit."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "regex or glob"},
                    "target": {"type": "string", "enum": ["content", "files"]},
                    "path": {"type": "string", "description": "dir to search in"},
                    "file_glob": {"type": "string", "description": "e.g. '*.py'"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": ["pattern"],
            },
            run=search_files,
            permission=Permission.AUTO,
        ),
    ]


def _resolve(workdir: Path, path_str: str) -> Path:
    from tlamati.tools.winpath import normalize_win_path

    p = Path(normalize_win_path(path_str)).expanduser()
    if not p.is_absolute():
        p = workdir / p
    return p.resolve()
