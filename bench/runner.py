"""bench/runner.py — E3b: tabla ARNÉS (mismo modelo, distinto arnés).

Corre las fixtures de fixtures/ con cada arnés headless contra OpenRouter
(MISMO modelo para todos los arneses, default qwen/qwen3-coder) y deja que
verify.py decida el éxito. Schema JSONL (E3c añade run + cost_usd, aditivo):

{task, harness, run, success, turns, tokens_in, tokens_out, cache_read,
 duration_s, cost_usd, error}

Campos que un arnés no expone = null honesto, NUNCA inventados (hermes -z no
expone tokens → cost_usd null, jamás estimado).

Reglas de integridad (anti-cheating, debugml.github.io):
- instruction única (contenido de instruction.md, sin ayudas añadidas);
- verify.py decide (exit 0 + VERIFY OK);
- timeouts sin tocar por arnés (HARNESS_TIMEOUT_S para todos);
- cero configuración especial: cada arnés corre con sus defaults headless.

Uso:
  python3 bench/runner.py --probe                 # 1 tarea barata por arnés (salud)
  python3 bench/runner.py --out evals/benchmark_2026-11-18/
  python3 bench/runner.py --harnesses tlamati,codex --tasks promedio,offbyone
  python3 bench/runner.py --runs 3 --model qwen/qwen3-coder --out evals/x/
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures"
BENCH_ROOT = Path("/tmp/tlamati-bench")
DEFAULT_MODEL = "qwen/qwen3-coder"
HARNESS_TIMEOUT_S = 600  # mismo techo para todos los arneses
VERIFY_TIMEOUT_S = 60
# CODEX_HOME NO puede estar bajo /tmp: codex rechaza crear helper binaries en
# dirs temporales ("Refusing to create helper binaries under temporary dir").
CODEX_HOME_DIR = Path.home() / ".cache" / "tlamati-bench-codex-home"

HARNESSES = ("tlamati", "opencode", "codex", "hermes")
# tarea de sonda: la más barata del corpus
PROBE_TASK = "promedio"

# Precios OpenRouter VERIFICADOS EN VIVO el 19-nov-2026 (USD por token).
# cache_read se descuenta de tokens_in (misma semántica acumulativa del schema).
# Modelo sin precios conocidos → cost_usd null honesto, NUNCA inventado.
PRICES: dict[str, tuple[float, float, float]] = {  # (in, out, cache_read)
    "qwen/qwen3-coder": (0.30e-6, 1.00e-6, 0.10e-6),
    "qwen/qwen3.8-flash": (0.15e-6, 0.47e-6, 0.016e-6),
    "deepseek/deepseek-v3.2": (0.26e-6, 0.38e-6, 0.13e-6),
    "moonshotai/kimi-k2.7-code": (0.65e-6, 3.50e-6, 0.16e-6),
}


def cost_usd(
    model: str, tokens_in: int | None, tokens_out: int | None, cache_read: int | None
) -> float | None:
    """Costo estimado USD. None si el arnés no expone tokens o el modelo no
    está en la tabla de precios (honesto, nunca inventado)."""
    prices = PRICES.get(model)
    if prices is None or tokens_in is None or tokens_out is None:
        return None
    p_in, p_out, p_cache = prices
    cread = cache_read or 0
    fresh_in = max(tokens_in - cread, 0)
    return round(fresh_in * p_in + cread * p_cache + tokens_out * p_out, 6)


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
    run: int
    success: bool
    turns: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read: int | None = None
    duration_s: float = 0.0
    cost_usd: float | None = None
    error: str | None = None


# Modelo activo de la corrida (lo fija main(); los constructores de comando lo
# leen — bench/runner.py es un script externo, no parte del paquete).
MODEL = DEFAULT_MODEL


# ---------------------------------------------------------------- arneses


def _cmd_tlamati(workdir: Path, instruction: str) -> list[str]:
    return [
        "tlamati",
        "-p",
        instruction,
        "--json",
        "--model",
        MODEL,
        "--approve-tool",
        "*",
        "--max-turns",
        "50",
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


def run_one(harness: str, task_dir: Path, api_key: str, run: int = 1) -> BenchResult:
    workdir = BENCH_ROOT / harness / task_dir.name
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(task_dir, workdir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
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
    tin, tout = metrics.get("tokens_in"), metrics.get("tokens_out")
    cread = metrics.get("cache_read")
    return BenchResult(
        task=task_dir.name,
        harness=harness,
        run=run,
        success=ok,
        turns=metrics.get("turns"),
        tokens_in=tin,
        tokens_out=tout,
        cache_read=cread,
        duration_s=round(duration, 2),
        cost_usd=cost_usd(MODEL, tin, tout, cread),
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
    global MODEL
    p = argparse.ArgumentParser(prog="bench-runner", description="E3b harness benchmark")
    p.add_argument("--harnesses", default=",".join(HARNESSES))
    p.add_argument("--tasks", help="coma-separada; default: todas")
    p.add_argument("--out", metavar="DIR", help="directorio de salida JSONL por arnés")
    p.add_argument(
        "--runs",
        type=int,
        default=1,
        help="réplicas por (arnés, tarea) para tasa de éxito y desviación (E3c)",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="modelo OpenRouter para TODOS los arneses (campaña de modelos E3c)",
    )
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
    MODEL = args.model
    if args.model not in PRICES and not args.probe:
        print(
            f"bench: aviso — modelo {args.model} sin precios en la tabla; "
            "cost_usd quedará null (honesto)",
            file=sys.stderr,
        )
    ensure_codex_home(api_key)
    runs = max(1, args.runs) if not args.probe else 1
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
            for run_idx in range(1, runs + 1):
                tag = f" run {run_idx}/{runs}" if runs > 1 else ""
                print(f"== {harness} / {task_dir.name}{tag} ==", file=sys.stderr, flush=True)
                r = run_one(harness, task_dir, api_key, run=run_idx)
                results.append(r)
                print(json.dumps(asdict(r), ensure_ascii=False), file=sys.stderr, flush=True)
                if is_upstream_error(r.error):
                    upstream_fail = True
        if out_dir:
            fp = out_dir / f"{harness}.jsonl"
            with open(fp, "w") as fh:
                for r in results:
                    fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
        _print_summary(harness, results, runs)

    if args.probe:
        return 1 if upstream_fail else 0
    return 0


def _print_summary(harness: str, results: list[BenchResult], runs: int) -> None:
    """Resumen por arnés: éxitos, pass@1 (todo run OK), costo y desviaciones."""
    n = len(results)
    ok_n = sum(1 for r in results if r.success)
    costo = sum(r.cost_usd for r in results if r.cost_usd is not None)
    dur = [r.duration_s for r in results]
    std_dur = statistics.stdev(dur) if len(dur) > 1 else 0.0
    print(
        f"[bench] {harness}: {ok_n}/{n} OK · costo ${costo:.4f} · "
        f"duración {sum(dur):.0f}s±{std_dur:.0f}",
        file=sys.stderr,
    )
    if runs > 1:
        # pass@1 conservador: la tarea cuenta solo si TODAS sus réplicas pasaron
        por_tarea: dict[str, list[bool]] = {}
        for r in results:
            por_tarea.setdefault(r.task, []).append(r.success)
        todas = sum(1 for v in por_tarea.values() if all(v))
        alguna = sum(1 for v in por_tarea.values() if any(v))
        print(
            f"[bench] {harness}: tareas {todas}/{len(por_tarea)} todas-las-réplicas "
            f"({alguna}/{len(por_tarea)} al menos una)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
