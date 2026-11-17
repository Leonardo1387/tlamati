"""CLI entry point.

Fase A: headless one-shot `tlamati -p "..."` contra OpenRouter (config.yaml o
defaults + OPENROUTER_API_KEY). TUI Textual llega en Fase E.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from tlamati import __version__
from tlamati.context.budget import Budget
from tlamati.context.compaction import CompactionConfig, Compactor, ModelSummarizer
from tlamati.core.loop import LoopResult, run_loop
from tlamati.policy.config import Policy, PolicyConfig
from tlamati.policy.ledger import Ledger
from tlamati.providers.openai_compat import OpenAICompat
from tlamati.sandbox.bwrap import bwrap_available
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry

DEFAULT_SYSTEM = (
    "Eres Tlamati, un agente de terminal local-first. Resuelve la tarea con las "
    "herramientas disponibles. Sé breve y directo. Trabaja en el directorio actual. "
    "Cuando termines, di TERMINADO y resume qué cambiaste."
)
DEFAULT_MODEL = "qwen/qwen3-coder"
DEFAULT_COMPACT_MODEL = "qwen/qwen3-coder"  # A6: modelo BARATO configurable (fallback chain)
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MAX_CONTEXT = 128_000

CONFIG_PATHS = (
    Path("tlamati.yaml"),
    Path.home() / ".config" / "tlamati" / "config.yaml",
)

DEFAULT_AUDIT_DB = Path.home() / ".local" / "share" / "tlamati" / "audit.db"


def load_config() -> dict[str, Any]:
    for p in CONFIG_PATHS:
        if p.is_file():
            with open(p) as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                return data
    return {}


def _resolve_api_key(cfg_provider: dict[str, Any]) -> str:
    key = cfg_provider.get("api_key_env") or "OPENROUTER_API_KEY"
    value = os.environ.get(key, "")
    if not value:
        # fallback dev: ~/.hermes/.env (misma máquina, mismo dueño)
        env_file = Path.home() / ".hermes" / ".env"
        prefix = f"{key}="
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                if line.startswith(prefix):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tlamati",
        description="Local-first, provider-agnostic agentic harness.",
    )
    p.add_argument("--version", action="version", version=f"tlamati {__version__}")
    p.add_argument(
        "-p",
        "--prompt",
        metavar="TEXT",
        help="Headless one-shot prompt",
    )
    p.add_argument("--model", metavar="ID", help=f"model id (default: {DEFAULT_MODEL})")
    p.add_argument("--base-url", metavar="URL", help="provider base URL (default: OpenRouter)")
    p.add_argument("--max-turns", type=int, default=20, help="turn budget (default: 20)")
    p.add_argument(
        "--max-context",
        type=int,
        default=DEFAULT_MAX_CONTEXT,
        help=f"context window tokens for budget (default: {DEFAULT_MAX_CONTEXT})",
    )
    p.add_argument(
        "--compact-model",
        metavar="ID",
        help=f"cheap model for compaction summaries (default: {DEFAULT_COMPACT_MODEL}; "
        "comma-separated list = fallback chain)",
    )
    p.add_argument(
        "--no-compact",
        action="store_true",
        help="disable compaction (budget_exceeded stops the loop immediately)",
    )
    p.add_argument(
        "--no-sandbox",
        action="store_true",
        help="disable the bwrap jail for the terminal tool (default: ON when bwrap exists)",
    )
    p.add_argument(
        "--sandbox-net",
        action="store_true",
        help="allow network inside the bwrap jail (default: network OFF)",
    )
    p.add_argument(
        "--approve-tool",
        metavar="NAME",
        action="append",
        default=[],
        help="headless: pre-approve a tool for ASK permissions ('*' = all; default: NEVER yolo)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="suppress streaming output",
    )
    p.add_argument(
        "--audit-db",
        metavar="PATH",
        help=f"audit ledger SQLite path (default: {DEFAULT_AUDIT_DB})",
    )
    p.add_argument(
        "--no-audit",
        action="store_true",
        help="disable the audit ledger for this run",
    )
    p.add_argument("cmd", nargs="?", help="subcommand: 'audit' (see --session)")
    p.add_argument("--session", metavar="ID", help="session id for `tlamati audit`")
    return p


def _ledger_wrapper(ledger: Ledger | None, quiet: bool) -> Any:
    """on_event que alimenta el ledger (turno + costos) y luego imprime."""
    printer = _printer(quiet)

    def on_event(kind: str, data: dict[str, Any]) -> None:
        if ledger is not None and kind == "turn_end":
            ledger.turn = data["turn"]
            u = data["usage"]
            ledger.record_turn_cost(
                turn=data["turn"],
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cache_read=u.cache_read_tokens,
                cost_usd=u.cost_usd,
            )
        printer(kind, data)

    return on_event


def _run_audit(args: argparse.Namespace) -> int:
    db = Path(args.audit_db) if args.audit_db else DEFAULT_AUDIT_DB
    if not db.is_file():
        print(f"tlamati audit: no existe el ledger {db} (¿corriste tlamati -p?)", file=sys.stderr)
        return 2
    if not args.session:
        sessions = Ledger.list_sessions(db)
        if not sessions:
            print("tlamati audit: ledger vacío.", file=sys.stderr)
            return 2
        print(f"sesiones en {db}:")
        for sid, n, ts in sessions[:20]:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            print(f"  {sid}  eventos={n}  último={when}")
        print("usa: tlamati audit --session <id>")
        return 0
    events, costs = Ledger.read_session(db, args.session)
    if not events and not costs:
        print(f"tlamati audit: sesión {args.session!r} no encontrada en {db}", file=sys.stderr)
        return 2
    print(f"== auditoría sesión {args.session} ({len(events)} eventos) ==")
    for e in events:
        t = time.strftime("%H:%M:%S", time.localtime(e.ts))
        flags = "".join(
            f for f, on in ((" E", e.is_error), (" U", e.untrusted), (" T", e.truncated)) if on
        )
        print(f"[{t}] t{e.turn} {e.decision:<13} {e.tool} {e.args_json[:100]}{flags}")
        if e.result_sha256:
            print(f"         sha256={e.result_sha256[:16]}…")
    if costs:
        tin = sum(c.input_tokens for c in costs)
        tout = sum(c.output_tokens for c in costs)
        tcr = sum(c.cache_read for c in costs)
        print(f"-- turnos={len(costs)} tokens: in={tin} out={tout} cache_read={tcr}")
    return 0


def _headless_approver(approved_tools: list[str]) -> Any:
    """Approver headless (B4): aprueba SOLO tools pre-aprobadas con
    --approve-tool (o '*' = todas). Lista vacía = nada se aprueba → ASK
    devuelve error honesto. Default NUNCA yolo (GUIA §B4). El TUI de Fase E
    traerá el prompt interactivo real."""
    allow_all = "*" in approved_tools
    allowed = set(approved_tools)

    async def approver(name: str, args: dict[str, Any]) -> bool:
        if allow_all or name in allowed:
            print(f"[policy] tool {name!r} pre-aprobada vía --approve-tool", file=sys.stderr)
            return True
        return False

    return approver


def _printer(quiet: bool) -> Any:
    def on_event(kind: str, data: dict[str, Any]) -> None:
        if quiet:
            return
        if kind == "text":
            print(data["text"], end="", flush=True)
        elif kind == "tool_run":
            args = str(data["args"])
            print(f"\n[tool] {data['name']} {args[:160]}", file=sys.stderr, flush=True)
        elif kind == "tool_result" and data.get("is_error"):
            print("[tool] ERROR (ver transcript)", file=sys.stderr, flush=True)
        elif kind == "turn_end":
            u = data["usage"]
            print(
                f"\n[turn {data['turn']}] in={u.input_tokens} out={u.output_tokens}",
                file=sys.stderr,
                flush=True,
            )
        elif kind == "budget":
            print(data["breakdown"], file=sys.stderr, flush=True)
        elif kind == "compaction":
            print(
                f"[compaction] micro={data['microcompacted']} "
                f"resumidos={data['summarized']} "
                f"tokens {data['tokens_before']}→{data['tokens_after']}"
                + (" (resumen FALLÓ: ventana nueva)" if data["summary_failed"] else ""),
                file=sys.stderr,
                flush=True,
            )

    return on_event


async def _run_headless(args: argparse.Namespace) -> int:
    cfg = load_config()
    cfg_provider = cfg.get("provider") or {}
    model = args.model or cfg_provider.get("model") or DEFAULT_MODEL
    base_url = args.base_url or cfg_provider.get("base_url") or DEFAULT_BASE_URL
    api_key = _resolve_api_key(cfg_provider)
    if not api_key:
        print(
            "tlamati: falta la API key (OPENROUTER_API_KEY o config provider.api_key_env)",
            file=sys.stderr,
        )
        return 2

    provider = OpenAICompat(model=model, base_url=base_url, api_key=api_key)
    sandbox = not args.no_sandbox
    if sandbox and not bwrap_available():
        print(
            "tlamati: bwrap NO instalado — el terminal correrá SIN sandbox "
            "(instalalo con: sudo apt install bubblewrap)",
            file=sys.stderr,
        )
    try:
        policy = Policy(PolicyConfig.from_dict(cfg.get("permissions")))
    except ValueError as e:
        print(f"tlamati: configuración de permisos inválida: {e}", file=sys.stderr)
        return 2
    ledger: Ledger | None = None
    session_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    if not args.no_audit:
        db = Path(args.audit_db) if args.audit_db else DEFAULT_AUDIT_DB
        try:
            ledger = Ledger(db, session_id)
        except sqlite3.Error as e:  # auditoría rota no impide correr
            print(
                f"tlamati: ledger de auditoría no disponible ({e}); sigo sin auditoría",
                file=sys.stderr,
            )
    tools = Registry(
        make_tools(Path.cwd(), sandbox=sandbox, sandbox_net=args.sandbox_net),
        approver=_headless_approver(args.approve_tool),
        policy=policy,
        ledger=ledger,
    )
    budget = Budget(max_context_tokens=args.max_context)

    compactor: Compactor | None = None
    if not args.no_compact:
        cfg_compact = cfg.get("compaction") or {}
        chain = args.compact_model or cfg_compact.get("model") or DEFAULT_COMPACT_MODEL
        summarizer = ModelSummarizer(
            [
                OpenAICompat(model=m.strip(), base_url=base_url, api_key=api_key)
                for m in str(chain).split(",")
                if m.strip()
            ]
        )
        compactor = Compactor(CompactionConfig(), summarizer)

    result: LoopResult = await run_loop(
        provider,
        system=cfg.get("system_prompt") or DEFAULT_SYSTEM,
        user_prompt=args.prompt,
        tools=tools,
        budget=budget,
        max_turns=args.max_turns,
        on_event=_ledger_wrapper(ledger, args.quiet),
        compactor=compactor,
    )
    if not args.quiet:
        print("", flush=True)
    u = result.usage
    print(
        f"[fin] stop={result.stop_reason} turnos={result.turns} "
        f"tokens: in={u.input_tokens} out={u.output_tokens} "
        f"cache_read={u.cache_read_tokens}",
        file=sys.stderr,
    )
    if result.error:
        print(f"[error] {result.error}", file=sys.stderr)
    if ledger is not None:
        if ledger.broken:
            print(f"[audit] ATENCIÓN: writes al ledger fallaron: {ledger.broken}", file=sys.stderr)
        print(
            f"[audit] sesión {session_id} — ver: tlamati audit --session {session_id}",
            file=sys.stderr,
        )
        ledger.close()
    return 0 if result.stop_reason in ("end_turn",) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "audit":
        return _run_audit(args)
    if args.cmd is not None:
        print(f"tlamati: subcomando desconocido {args.cmd!r} (existe: audit)", file=sys.stderr)
        return 2
    if args.prompt:
        return asyncio.run(_run_headless(args))
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
