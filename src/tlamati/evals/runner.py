"""tlamati-eval — A7: runner de tareas terminal-bench-lite.

Recorre fixtures/ (cada una: repo semilla con bug + instruction.md +
verify.py ejecutable), copia cada tarea a un workspace temporal, corre
run_loop headless y verifica con verify.py. Emite JSONL por tarea:
{task, success, turns, tokens_in, tokens_out, cache_read, cost_usd,
stop_reason, duration_s, error}.

El baseline se guarda en evals/baseline_<fecha>.jsonl (F10 evals+trazas;
ratchet de Osmani: si una fase futura rompe el baseline, se detiene y revisa).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tlamati.cli import DEFAULT_BASE_URL, DEFAULT_MODEL, _resolve_api_key, load_config
from tlamati.context.budget import Budget
from tlamati.core.loop import LoopResult, run_loop
from tlamati.providers.base import Provider
from tlamati.providers.openai_compat import OpenAICompat
from tlamati.tools_min.mini import make_tools

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURES = REPO_ROOT / "fixtures"
SYSTEM = (
    "Eres Tlamati, un agente de terminal local-first. Resuelve la tarea con las "
    "herramientas disponibles. Sé breve y directo. Trabaja en el directorio actual. "
    "Cuando termines, di TERMINADO y resume qué cambiaste."
)


@dataclass
class TaskResult:
    """Una línea del JSONL — schema congelado del baseline (F10)."""

    task: str
    success: bool
    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read: int = 0
    cost_usd: float | None = None
    stop_reason: str = ""
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class EvalSummary:
    results: list[TaskResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.success)


def discover_tasks(fixtures_dir: Path, only: str | None = None) -> list[Path]:
    """Tareas = subdirectorios con instruction.md + verify.py (orden estable)."""
    tasks = [
        d
        for d in sorted(fixtures_dir.iterdir())
        if d.is_dir() and (d / "instruction.md").is_file() and (d / "verify.py").is_file()
    ]
    if only:
        tasks = [t for t in tasks if t.name == only]
    return tasks


def _verify(workdir: Path, timeout_s: int = 60) -> tuple[bool, str]:
    """verify.py decide el éxito: exit 0 + 'VERIFY OK' (explícito, no supuesto)."""
    try:
        proc = subprocess.run(
            [sys.executable, "verify.py"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False, "verify.py timeout"
    out = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0 and "VERIFY OK" in proc.stdout, out[-500:]


async def run_task(
    task_dir: Path,
    workspace_root: Path,
    *,
    provider: Provider,
    max_turns: int,
    max_context: int,
) -> TaskResult:
    """Copia la semilla a un workspace limpio → loop → verify."""
    workdir = workspace_root / task_dir.name
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(task_dir, workdir)
    instruction = (workdir / "instruction.md").read_text()

    t0 = time.monotonic()
    try:
        result: LoopResult = await run_loop(
            provider,
            system=SYSTEM,
            user_prompt=instruction,
            tools=make_tools(workdir),
            budget=Budget(max_context_tokens=max_context),
            max_turns=max_turns,
            on_event=_task_printer(task_dir.name),
        )
        loop_error: str | None = result.error
        loop_result = result
    except Exception as e:
        loop_error = f"{type(e).__name__}: {e}"
        loop_result = None
    duration = time.monotonic() - t0

    ok, verify_out = _verify(workdir)
    usage = loop_result.usage if loop_result else None
    return TaskResult(
        task=task_dir.name,
        success=ok,
        turns=loop_result.turns if loop_result else 0,
        tokens_in=usage.input_tokens if usage else 0,
        tokens_out=usage.output_tokens if usage else 0,
        cache_read=usage.cache_read_tokens if usage else 0,
        cost_usd=usage.cost_usd if usage else None,
        stop_reason=loop_result.stop_reason if loop_result else "crash",
        duration_s=round(duration, 2),
        error=loop_error or (None if ok else verify_out),
    )


def _task_printer(name: str) -> Any:
    def on_event(kind: str, data: dict[str, Any]) -> None:
        if kind == "tool_run":
            print(f"  [{name}][tool] {data['name']} {str(data['args'])[:100]}", file=sys.stderr)
        elif kind == "turn_end":
            print(f"  [{name}][turn {data['turn']}]", file=sys.stderr)

    return on_event


async def run_eval(args: argparse.Namespace) -> int:
    fixtures_dir = Path(args.fixtures) if args.fixtures else DEFAULT_FIXTURES
    tasks = discover_tasks(fixtures_dir, args.task)
    if not tasks:
        print(f"tlamati-eval: sin tareas en {fixtures_dir}", file=sys.stderr)
        return 2

    cfg = load_config()
    cfg_provider = cfg.get("provider") or {}
    model = args.model or cfg_provider.get("model") or DEFAULT_MODEL
    base_url = args.base_url or cfg_provider.get("base_url") or DEFAULT_BASE_URL
    api_key = _resolve_api_key(cfg_provider)
    if not api_key:
        print("tlamati-eval: falta la API key (OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    provider = OpenAICompat(model=model, base_url=base_url, api_key=api_key)

    workspace_root = Path(args.workspace) if args.workspace else Path("/tmp/tlamati-eval")
    workspace_root.mkdir(parents=True, exist_ok=True)

    summary = EvalSummary()
    out_path = Path(args.out) if args.out else None
    out_fh = open(out_path, "w") if out_path else None  # noqa: SIM115
    try:
        for task_dir in tasks:
            print(f"== {task_dir.name} ==", file=sys.stderr)
            r = await run_task(
                task_dir,
                workspace_root,
                provider=provider,
                max_turns=args.max_turns,
                max_context=args.max_context,
            )
            summary.results.append(r)
            line = json.dumps(asdict(r), ensure_ascii=False)
            print(line, file=sys.stderr if out_fh else sys.stdout)
            if out_fh:
                out_fh.write(line + "\n")
    finally:
        if out_fh:
            out_fh.close()

    print(
        f"[eval] {summary.passed}/{len(summary.results)} OK · modelo={model}",
        file=sys.stderr,
    )
    return 0 if summary.passed == len(summary.results) else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tlamati-eval", description="A7 eval runner (JSONL)")
    p.add_argument("--fixtures", metavar="DIR", help=f"default: {DEFAULT_FIXTURES}")
    p.add_argument("--task", metavar="NAME", help="corre una sola tarea")
    p.add_argument("--model", metavar="ID", help=f"default: {DEFAULT_MODEL}")
    p.add_argument("--base-url", metavar="URL", help="default: OpenRouter")
    p.add_argument("--workspace", metavar="DIR", help="default: /tmp/tlamati-eval")
    p.add_argument("--out", metavar="FILE", help="JSONL output file (default: stdout)")
    p.add_argument("--max-turns", type=int, default=12)
    p.add_argument("--max-context", type=int, default=128_000)
    args = p.parse_args(argv)
    return asyncio.run(run_eval(args))


if __name__ == "__main__":
    raise SystemExit(main())
