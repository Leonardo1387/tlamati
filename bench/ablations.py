# ruff: noqa: RUF001  (informe en espanol con signos intencionales)
"""bench/ablations.py — FASE 1 del moat: H8 CAUSAL por ablación.

Pregunta: ¿de dónde sale la ventaja de tokens? Se apaga UN componente a la vez
y se mide cuánto sube el consumo. Configs (handoff MOAT H6-H9, FASE 1):

  A0_base       : tlamati tal cual (línea base)
  A1_no_compact : --no-compact (apaga compactación de presupuesto)
  A3_prefijo_30k: AGENTS.md falso de ~30k tokens en la COPIA del workspace
                  (el loader C4 lo inyecta al prefijo cada turno; la fixture
                  original NO se toca — verificado en handoff: verify.py corre
                  en la copia y AGENTS.md es inerte para los checks)

A2 (truncado M1 de 50k) se DOCUMENTA COMO NO ABLABLE sin tocar el binario:
el binario instalado es pre-fixes-s24 a propósito (regla de campaña) y el
truncado solo dispara con tool results >50k chars, raros en fixtures baratas.

Reglas heredadas: mismo techo 600s, verify.py decide, null honesto, costos =
PRICES estimada (NO factura). --runs 1 por celda (20 corridas ≈ $3-5).

Uso:
  python3 bench/ablations.py --list          # plan sin gastar
  python3 bench/ablations.py --probe         # sonda upstream (1 corrida A0)
  python3 bench/ablations.py                 # matriz completa
  python3 bench/ablations.py --configs A0_base,A3_prefijo_30k --tasks promedio
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # mismo directorio; runner no es paquete

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures"
ABL_ROOT = Path("/tmp/tlamati-ablations")
OUT_DIR = REPO / "evals" / f"ablations_{time.strftime('%Y-%m-%d')}"
DEFAULT_MODEL = "qwen/qwen3-coder"
TASKS_BARATAS = [
    "promedio",
    "offbyone",
    "conversor",
    "import_roto",
    "crear_modulo",
]
# ~30k tokens de prefijo extra ≈ 120k chars (proxy bytes/4 validado 19-nov).
# Contenido INERTE: guía de estilo repetitiva que no cambia la conducta ante la
# tarea (si cambiara el éxito, la ablación estaría contaminada — se reporta ok/n).
_INFLATE_CHARS = 120_000
_INFLATE_UNIT = (
    "## Sección {n} — Guía de estilo del proyecto\n\n"
    "Mantén el código simple y legible. Usa nombres descriptivos en español o "
    "inglés de forma consistente. No añadas dependencias nuevas sin necesidad. "
    "Prefiere funciones puras y cortas. Documenta las decisiones no obvias con "
    "un comentario de una línea. Evita la duplicación; extrae helpers cuando "
    "una lógica aparezca dos veces. Los errores se propagan con mensajes "
    "honestos, nunca se silencian.\n\n"
)


@dataclass
class Config:
    name: str
    extra_flags: list[str]
    inflate_agents_md: bool


CONFIGS = [
    Config("A0_base", [], False),
    Config("A1_no_compact", ["--no-compact"], False),
    Config("A3_prefijo_30k", [], True),
]


def make_agents_md() -> str:
    parts: list[str] = ["# AGENTS.md — convenciones del repositorio\n\n"]
    n = 0
    total = sum(len(p) for p in parts)
    while total < _INFLATE_CHARS:
        n += 1
        unit = _INFLATE_UNIT.format(n=n)
        parts.append(unit)
        total += len(unit)
    return "".join(parts)


def run_cell(cfg: Config, task_dir: Path, model: str, api_key: str, run: int = 1) -> dict[str, Any]:
    """Una corrida tlamati con la configuración de ablación aplicada."""
    workdir = ABL_ROOT / cfg.name / task_dir.name
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(task_dir, workdir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    setup = workdir / "setup.sh"
    if setup.is_file():
        with contextlib.suppress(subprocess.TimeoutExpired, OSError):
            subprocess.run(
                ["bash", str(setup)], cwd=workdir, capture_output=True, text=True, timeout=120
            )
    if cfg.inflate_agents_md:
        (workdir / "AGENTS.md").write_text(make_agents_md())

    instruction = (workdir / "instruction.md").read_text()
    cmd = [
        "tlamati",
        "-p",
        instruction,
        "--json",
        "--model",
        model,
        "--approve-tool",
        "*",
        "--max-turns",
        "50",
        "--no-session",
        *cfg.extra_flags,
    ]
    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = api_key

    t0 = time.monotonic()
    error: str | None = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=runner.HARNESS_TIMEOUT_S,
        )
        stdout = proc.stdout
        stderr = proc.stderr or ""
        if proc.returncode != 0:
            error = f"rc={proc.returncode}: {(stderr or stdout).strip()[-300:]}"
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout if isinstance(e.stdout, str) else ""
        error = f"timeout >{runner.HARNESS_TIMEOUT_S}s"
    duration = time.monotonic() - t0

    raw_dir = OUT_DIR / "_raw" / cfg.name
    with contextlib.suppress(OSError):
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{task_dir.name}.run{run}.jsonl").write_text(stdout)
        (raw_dir / f"{task_dir.name}.run{run}.stderr").write_text(stderr)

    ok, verify_out = runner.verify(workdir)
    metrics = runner._extract_tlamati(stdout)
    tin, tout = metrics.get("tokens_in"), metrics.get("tokens_out")
    cread = metrics.get("cache_read")
    return {
        "config": cfg.name,
        "task": task_dir.name,
        "run": run,
        "model": model,
        "success": ok,
        "turns": metrics.get("turns"),
        "tokens_in": tin,
        "tokens_out": tout,
        "cache_read": cread,
        "duration_s": round(duration, 2),
        "cost_usd": runner.cost_usd(model, tin, tout, cread),
        "error": error or metrics.get("error") or (None if ok else verify_out),
    }


def probe(model: str, api_key: str) -> int:
    task = FIXTURES / "promedio"
    print(f"sonda: A0_base × promedio × {model} …")
    row = run_cell(CONFIGS[0], task, model, api_key)
    print(json.dumps(row, ensure_ascii=False))
    if row["error"] and runner.is_upstream_error(row["error"]):
        print("UPSTREAM ENFERMO — no lanzar la matriz (regla S17)")
        return 1
    return 0


def summary(rows: list[dict[str, Any]]) -> None:
    print(f"\n{'config':18} {'ok/n':>6} {'tin μ':>10} {'Δ vs A0':>9} {'$ total':>9}")
    base: dict[str, dict[str, int]] = {}
    for cfg in CONFIGS:
        sel = [r for r in rows if r["config"] == cfg.name]
        if not sel:
            continue
        per_task: dict[str, list[int]] = {}
        for r in sel:
            if r.get("tokens_in"):
                per_task.setdefault(r["task"], []).append(r["tokens_in"])
        base[cfg.name] = {t: int(statistics.mean(v)) for t, v in per_task.items()}
        tin_mu = (
            statistics.mean([r["tokens_in"] for r in sel if r.get("tokens_in")])
            if any(r.get("tokens_in") for r in sel)
            else None
        )
        cost = sum(r["cost_usd"] for r in sel if r.get("cost_usd") is not None)
        ok = sum(1 for r in sel if r["success"])
        tin_s = f"{tin_mu:,.0f}" if tin_mu else "null"
        if cfg.name == "A0_base":
            delta = "—"
        elif tin_mu and base.get("A0_base"):
            a0 = statistics.mean(base["A0_base"].values())
            delta = f"{(tin_mu / a0 - 1) * 100:+.0f}%" if a0 else "n/d"
        else:
            delta = "n/d"
        print(f"{cfg.name:18} {ok:>3}/{len(sel):<2} {tin_s:>10} {delta:>9} ${cost:>8.4f}")
    # contribución por tarea (A3 vs A0, el efecto prefijo puro)
    if base.get("A0_base") and base.get("A3_prefijo_30k"):
        print("\ncontribución por tarea (tin medio A3 − A0):")
        for t in sorted(set(base["A0_base"]) & set(base["A3_prefijo_30k"])):
            d = base["A3_prefijo_30k"][t] - base["A0_base"][t]
            print(f"  {t:28} {d:>+10,} tokens")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ablations", description="H8 causal por ablación")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tasks", help="coma-separada; default: 5 baratas")
    ap.add_argument("--configs", help="coma-separada; default: todas")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--list", action="store_true", help="imprimir plan y salir ($0)")
    args = ap.parse_args(argv)

    tasks_names = args.tasks.split(",") if args.tasks else TASKS_BARATAS
    cfg_names = args.configs.split(",") if args.configs else [c.name for c in CONFIGS]
    configs = [c for c in CONFIGS if c.name in cfg_names]
    tasks = [FIXTURES / t for t in tasks_names]
    missing = [str(t) for t in tasks if not (t / "instruction.md").is_file()]
    if missing:
        print(f"fixtures inexistentes: {missing}")
        return 2

    if args.list:
        print(
            f"plan: {len(configs)} configs × {len(tasks)} tareas × {args.runs} runs "
            f"= {len(configs) * len(tasks) * args.runs} corridas ({args.model})"
        )
        for c in configs:
            flags = " ".join(c.extra_flags) or "(defaults)"
            extra = " + AGENTS.md ~30k tok" if c.inflate_agents_md else ""
            print(f"  {c.name:18} {flags}{extra}")
        return 0

    api_key = runner.resolve_api_key()
    if not api_key:
        print("sin OPENROUTER_API_KEY (env o ~/.hermes/.env)")
        return 2
    if args.probe:
        return probe(args.model, api_key)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / "ablations.jsonl"
    rows: list[dict[str, Any]] = []
    n_cells = len(configs) * len(tasks) * args.runs
    i = 0
    with out_file.open("a") as fh:
        for cfg in configs:
            for task in tasks:
                for run in range(1, args.runs + 1):
                    i += 1
                    print(f"[{i}/{n_cells}] {cfg.name} × {task.name} run{run} …", flush=True)
                    row = run_cell(cfg, task, args.model, api_key, run)
                    rows.append(row)
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                    if row["error"] and runner.is_upstream_error(row["error"]):
                        print("UPSTREAM ENFERMO a mitad de matriz — paro honesto;")
                        print("relanzar cuando respire (idempotente: lee ablations.jsonl)")
                        summary(rows)
                        return 1
    summary(rows)
    print(f"\nJSONL: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
