"""bench/runner.py — E3b: tabla ARNÉS (mismo modelo, distinto arnés).

Corre las 10 fixtures de fixtures/ con cada arnés headless contra OpenRouter
(qwen/qwen3-coder, MISMO modelo para todos) y deja que verify.py decida el
éxito. Schema JSONL congelado (mismo espíritu que evals/runner.py):

{task, harness, success, turns, tokens_in, tokens_out, cache_read,
 duration_s, error}

Campos que un arnés no expone = null honesto, NUNCA inventados.

Reglas de integridad (anti-cheating, debugml.github.io):
- instruction única (contenido de instruction.md, sin ayudas añadidas);
- verify.py decide (exit 0 + VERIFY OK);
- timeouts sin tocar por arnés (HARNESS_TIMEOUT_S para todos);
- cero configuración especial: cada arnés corre con sus defaults headless.

Uso:
  python3 bench/runner.py --probe                 # 1 tarea barata por arnés (salud)
  python3 bench/runner.py --out evals/benchmark_2026-11-18/
  python3 bench/runner.py --harnesses tlamati,codex --tasks promedio,offbyone
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures"
BENCH_ROOT = Path("/tmp/tlamati-bench")
MODEL = "qwen/qwen3-coder"
HARNESS_TIMEOUT_S = 600  # mismo techo para todos los arneses
VERIFY_TIMEOUT_S = 60
CODEX_HOME_DIR = Path("/tmp/tlamati-bench-codex-home")

HARNESSES = ("tlamati", "opencode", "codex", "hermes")
# tarea de sonda: la más barata del corpus
PROBE_TASK = "promedio"


def resolve_api_key() -> str:
    """OPENROUTER_API_KEY del env o de ~/.hermes/.env (misma máquina, mismo dueño)."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def ensure_codex_home(api_key: str) -> None:
    """CODEX_HOME aparte con provider OpenRouter (no toca ~/.codex del usuario)."""
    CODEX_HOME_DIR.mkdir(parents=True, exist_ok=True)
    (CODEX_HOME_DIR / "config.toml").write_text(
        f"""model = "{MODEL}"
model_provider = "openrouter"
approval_policy = "never"

[model_providers.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
env_key = "OPENROUTER_API_KEY"
wire_api = "responses"
"""
    )
    # codex exige auth.json presente aunque use env_key
    auth = CODEX_HOME_DIR / "auth.json"
    if not auth.exists():
        auth.write_text(json.dumps({"OPENAI_API_KEY": api_key}))


@dataclass
class BenchResult:
    task: str
    harness: str
    success: bool
    turns: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read: int | None = None
    duration_s: float = 0.0
    error: str | None = None


# ---------------------------------------------------------------- arneses


def _cmd_tlamati(workdir: Path, instruction: str) -> list[str]:
    return [
        "tlamati",
        "-p",
        instruction,
        "--json",
        "--approve-tool",
        "*",
        "--max-turns",
        "20",
        "--no-session",
    ]


def _cmd_opencode(workdir: Path, instruction: str) -> list[str]:
    return [
        "opencode",
        "run",
        instruction,
        "--dir",
        str(workdir),
        "--auto",
        "--format",
        "json",
        "-m",
        f"openrouter/{MODEL}",
    ]


def _cmd_codex(workdir: Path, instruction: str) -> list[str]:
    return [
        "codex",
        "exec",
        "-C",
        str(workdir),
        "-s",
        "workspace-write",
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        instruction,
    ]


def _cmd_hermes(workdir: Path, instruction: str) -> list[str]:
    return [
        "hermes",
        "-z",
        instruction,
        "--safe-mode",
        "--yolo",
        "-m",
        MODEL,
        "--provider",
        "openrouter",
    ]


COMMANDS = {
    "tlamati": _cmd_tlamati,
    "opencode": _cmd_opencode,
    "codex": _cmd_codex,
    "hermes": _cmd_hermes,
}


def _deep_find(obj: Any, key: str) -> Any:
    """Primera aparición de `key` en un JSON anidado (fail-soft)."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            hit = _deep_find(v, key)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _deep_find(v, key)
            if hit is not None:
                return hit
    return None


def _parse_jsonl_events(stdout: str) -> list[dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        with contextlib.suppress(json.JSONDecodeError):
            events.append(json.loads(line))
    return events


def _extract_tlamati(stdout: str) -> dict[str, Any]:
    for ev in reversed(_parse_jsonl_events(stdout)):
        if ev.get("event") == "result":
            usage = ev.get("usage") or {}
            return {
                "turns": ev.get("turns"),
                "tokens_in": usage.get("input_tokens"),
                "tokens_out": usage.get("output_tokens"),
                "cache_read": usage.get("cache_read_tokens"),
                "error": ev.get("error"),
            }
    return {}


def _extract_codex(stdout: str) -> dict[str, Any]:
    """codex exec --json (0.133.x): JSONL con thread.started/turn.started/
    item.*/turn.completed. El usage ACUMULADO viene en turn.completed:
    {input_tokens (INCLUYE cached), cached_input_tokens, output_tokens} —
    misma semántica que los input_tokens de tlamati vía OpenRouter."""
    events = _parse_jsonl_events(stdout)
    out: dict[str, Any] = {}
    for e in reversed(events):
        if e.get("type") == "turn.completed":
            usage = e.get("usage") or {}
            out["tokens_in"] = usage.get("input_tokens")
            out["tokens_out"] = usage.get("output_tokens")
            out["cache_read"] = usage.get("cached_input_tokens")
            break
    err = _deep_find(events[-1] if events else {}, "error")
    if isinstance(err, str):
        out["error"] = err
    return out


def _extract_opencode(stdout: str) -> dict[str, Any]:
    """opencode --format json: JSONL de eventos step_start/tool_use/text/step_finish.
    Los tokens vienen POR STEP en step_finish.part.tokens — se SUMAN para el total
    de la corrida (misma semántica acumulativa que tlamati/hermes).
    input de opencode EXCLUYE cache.read (OpenRouter) → tokens_in = input+cache.read
    para que sea comparable con los input_tokens de tlamati."""
    out: dict[str, Any] = {}
    events = _parse_jsonl_events(stdout)
    if not events:
        return out
    steps = [e for e in events if e.get("type") == "step_finish"]
    if steps:
        out["turns"] = len(steps)
        tin = tout = cread = 0
        for e in steps:
            tokens = ((e.get("part") or {}).get("tokens")) or {}
            cache = tokens.get("cache") or {}
            cache_read = cache.get("read") or 0
            tin += (tokens.get("input") or 0) + cache_read
            tout += tokens.get("output") or 0
            cread += cache_read
        out["tokens_in"] = tin
        out["tokens_out"] = tout
        out["cache_read"] = cread
    err = _deep_find(events[-1], "error")
    if isinstance(err, dict):
        err = err.get("message") or err.get("name")
    if isinstance(err, str) and err:
        out["error"] = err[:300]
    return out


def _extract_hermes(stdout: str) -> dict[str, Any]:
    # -z imprime SOLO texto final: sin tokens/turnos → nulls honestos
    return {}


EXTRACTORS = {
    "tlamati": _extract_tlamati,
    "codex": _extract_codex,
    "opencode": _extract_opencode,
    "hermes": _extract_hermes,
}


# ---------------------------------------------------------------- corrida


def verify(workdir: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "verify.py"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=VERIFY_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, "verify.py timeout"
    out = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0 and "VERIFY OK" in proc.stdout, out[-500:]


def run_one(harness: str, task_dir: Path, api_key: str) -> BenchResult:
    workdir = BENCH_ROOT / harness / task_dir.name
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(task_dir, workdir)
    setup = workdir / "setup.sh"
    if setup.is_file():
        with contextlib.suppress(subprocess.TimeoutExpired, OSError):
            subprocess.run(
                ["bash", str(setup)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=120,
            )
    instruction = (workdir / "instruction.md").read_text()

    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = api_key
    if harness == "codex":
        env["CODEX_HOME"] = str(CODEX_HOME_DIR)

    cmd = COMMANDS[harness](workdir, instruction)
    t0 = time.monotonic()
    error: str | None = None
    stdout = ""
    try:
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=HARNESS_TIMEOUT_S,
        )
        stdout = proc.stdout
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-300:]
            error = f"harness rc={proc.returncode}: {tail}"
    except subprocess.TimeoutExpired:
        error = f"harness timeout >{HARNESS_TIMEOUT_S}s"
    except FileNotFoundError as e:
        error = f"harness no instalado: {e}"
    duration = time.monotonic() - t0

    ok, verify_out = verify(workdir)
    metrics = EXTRACTORS[harness](stdout)
    return BenchResult(
        task=task_dir.name,
        harness=harness,
        success=ok,
        turns=metrics.get("turns"),
        tokens_in=metrics.get("tokens_in"),
        tokens_out=metrics.get("tokens_out"),
        cache_read=metrics.get("cache_read"),
        duration_s=round(duration, 2),
        error=error or metrics.get("error") or (None if ok else verify_out),
    )


def discover_tasks(only: list[str] | None) -> list[Path]:
    tasks = [
        d
        for d in sorted(FIXTURES.iterdir())
        if d.is_dir() and (d / "instruction.md").is_file() and (d / "verify.py").is_file()
    ]
    if only:
        tasks = [t for t in tasks if t.name in only]
    return tasks


def is_upstream_error(err: str | None) -> bool:
    if not err:
        return False
    marks = (
        "429",
        "504",
        "502",
        "rate limit",
        "rate-limited",
        "overloaded",
        "temporarily",
        "upstream",
        "ECONNRESET",
        "socket hang up",
    )
    low = err.lower()
    return any(m.lower() in low for m in marks)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bench-runner", description="E3b harness benchmark")
    p.add_argument("--harnesses", default=",".join(HARNESSES))
    p.add_argument("--tasks", help="coma-separada; default: todas")
    p.add_argument("--out", metavar="DIR", help="directorio de salida JSONL por arnés")
    p.add_argument(
        "--probe",
        action="store_true",
        help=f"sonda: solo {PROBE_TASK} por arnés (ver salud upstream)",
    )
    args = p.parse_args(argv)

    api_key = resolve_api_key()
    if not api_key:
        print("bench: falta OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    harnesses = [h.strip() for h in args.harnesses.split(",") if h.strip()]
    for h in harnesses:
        if h not in HARNESSES:
            print(f"bench: arnés desconocido {h}", file=sys.stderr)
            return 2
    ensure_codex_home(api_key)
    tasks = discover_tasks(
        [PROBE_TASK] if args.probe else (args.tasks.split(",") if args.tasks else None)
    )
    if not tasks:
        print("bench: sin tareas", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    upstream_fail = False
    for harness in harnesses:
        results: list[BenchResult] = []
        for task_dir in tasks:
            print(f"== {harness} / {task_dir.name} ==", file=sys.stderr, flush=True)
            r = run_one(harness, task_dir, api_key)
            results.append(r)
            print(json.dumps(asdict(r), ensure_ascii=False), file=sys.stderr, flush=True)
            if is_upstream_error(r.error):
                upstream_fail = True
        if out_dir:
            fp = out_dir / f"{harness}.jsonl"
            with open(fp, "w") as fh:
                for r in results:
                    fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
        ok_n = sum(1 for r in results if r.success)
        print(f"[bench] {harness}: {ok_n}/{len(results)} OK", file=sys.stderr)

    if args.probe:
        return 1 if upstream_fail else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
