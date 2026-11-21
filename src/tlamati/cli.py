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
from tlamati.context.instructions import load_instructions, render_for_prompt
from tlamati.context.routing import (
    Routing,
    load_routing,
)
from tlamati.context.routing import (
    render_for_prompt as render_routing_for_prompt,
)
from tlamati.core.json_events import (
    EXIT_USAGE,
    JsonlEmitter,
    exit_code_for,
    result_event,
)
from tlamati.core.loop import LoopResult, run_loop
from tlamati.core.messages import Message
from tlamati.mcp.client import close_mcp, load_mcp_servers, parse_mcp_config
from tlamati.memory.dream import dream
from tlamati.memory.skills import SkillLibrary, default_skill_roots, make_skill_tools
from tlamati.memory.store import MemoryStore, default_memory_dir, seed_if_empty
from tlamati.memory.tools import make_memory_tools
from tlamati.plan.mode import PLAN_MODE_PROMPT, PlanState
from tlamati.plan.tools import make_plan_tools
from tlamati.plugins import HookRegistry, load_plugins
from tlamati.policy.config import Policy, PolicyConfig
from tlamati.policy.ledger import Ledger
from tlamati.providers.openai_compat import OpenAICompat
from tlamati.sandbox.bwrap import bwrap_available
from tlamati.session.store import SessionStore
from tlamati.subagent.spawn import (
    DELEGATE_PROMPT_BLOCK,
    SubagentConfig,
    make_delegate_tool,
)
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
DEFAULT_SESSION_DB = Path.home() / ".local" / "share" / "tlamati" / "sessions.db"

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


def resolve_turn_limits(cfg: dict[str, Any], args: argparse.Namespace) -> tuple[int, int]:
    """E3d PASO B: flag > config general.* > default (60 turnos, 3 repeticiones).
    Mismos límites para headless Y TUI (pitfall #5 sesión 20)."""
    cfg_general = cfg.get("general") or {}

    def _int(flag: int | None, key: str, default: int) -> int:
        if flag is not None:
            return flag
        try:
            return int(cfg_general.get(key, default))
        except (TypeError, ValueError):
            return default

    return _int(args.max_turns, "max_turns", 60), _int(args.stall_repeats, "stall_repeats", 3)


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
    p.add_argument(
        "--max-turns",
        type=int,
        default=None,
        metavar="N",
        help="turn budget (default: config general.max_turns or 60; "
        "<=0 = yolo, sin muro — el presupuesto de contexto sigue siendo el techo)",
    )
    p.add_argument(
        "--stall-repeats",
        type=int,
        default=None,
        metavar="N",
        help="same tool call (identical args) N turns in a row = dead loop, "
        "hard stop with stop_reason=stall (default: config general.stall_repeats "
        "or 3; 0 disables)",
    )
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
        "--session-db",
        metavar="PATH",
        default=str(DEFAULT_SESSION_DB),
        help=f"SQLite session store path (default: {DEFAULT_SESSION_DB})",
    )
    p.add_argument(
        "--no-session",
        action="store_true",
        help="do not persist this run to the session store",
    )
    p.add_argument(
        "--continue",
        dest="continue_last",
        action="store_true",
        help="resume the most recent session (with -p: continue that conversation)",
    )
    p.add_argument(
        "--resume",
        metavar="SESSION_ID",
        help="resume a specific session by id",
    )
    p.add_argument(
        "--memory-dir",
        metavar="PATH",
        help="memory dir (default: ~/.local/share/tlamati/memory; project scope = .tlamati/memory)",
    )
    p.add_argument(
        "--no-memory",
        action="store_true",
        help="disable durable memory (no prefix injection, no memory tools)",
    )
    p.add_argument(
        "--dream",
        action="store_true",
        help="consolidate memory with a cheap model at session close (auto-dream, CC donor)",
    )
    p.add_argument(
        "--skills-dir",
        metavar="PATH",
        action="append",
        default=[],
        help="extra skills directory (repeatable; hermes-compatible — e.g. "
        "--skills-dir ~/.hermes/skills migrates an existing library with 1 flag)",
    )
    p.add_argument(
        "--no-instructions",
        action="store_true",
        help="do not inject AGENTS.md/CLAUDE.md project instructions",
    )
    p.add_argument(
        "--workspace",
        metavar="NAME",
        help="force the active routing workspace (C6; default: first fnmatch of the task)",
    )
    p.add_argument(
        "--no-routing",
        action="store_true",
        help="disable .tlamati/routing.md workspace routing",
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
    p.add_argument(
        "--plan-mode",
        action="store_true",
        help="start the run in plan-mode (explore→approve→execute; write/terminal "
        "DENIED until the user approves a plan; mutually exclusive with --approve-tool '*')",
    )
    p.add_argument(
        "--no-subagents",
        action="store_true",
        help="disable the delegate_task tool (D1 subagents)",
    )
    p.add_argument(
        "--plugins-dir",
        metavar="PATH",
        action="append",
        default=[],
        help="extra plugins directory (repeatable; *.py modules with register(hooks))",
    )
    p.add_argument(
        "--no-plugins",
        action="store_true",
        help="disable plugin discovery (the internal audit plugin is NEVER disabled)",
    )
    p.add_argument(
        "--mcp-config",
        metavar="PATH",
        help="override yaml file with an 'mcp:' section "
        "(default: tlamati.yaml / ~/.config/tlamati/config.yaml)",
    )
    p.add_argument(
        "--no-mcp",
        action="store_true",
        help="disable MCP servers for this run (kill switch)",
    )
    p.add_argument("--quiet", action="store_true", help="suppress streaming output")
    p.add_argument(
        "--json",
        action="store_true",
        help="E2: machine mode — JSONL events on stdout (one JSON object per "
        "line, final `result` event) + honest exit codes, for CI/scripts",
    )
    p.add_argument(
        "cmd",
        nargs="?",
        choices=["sessions", "audit", "model"],
        help=(
            "'sessions' = list stored sessions; 'audit' = read the audit ledger; "
            "'model' = wizard interactivo proveedor->modelo->config (no LLM, free)"
        ),
    )
    p.add_argument("--session", metavar="ID", help="session id for `tlamati audit`")
    return p


def _ledger_wrapper(ledger: Ledger | None, quiet: bool, emitter: JsonlEmitter | None = None) -> Any:
    """on_event que alimenta el ledger (turno + costos) y luego publica.

    E2: con emitter (--json), los eventos salen como JSONL a stdout y el
    printer humano se omite por completo (stdout es EXCLUSIVO del stream).
    Sin emitter, comportamiento idéntico al pre-E2."""
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
        if emitter is not None:
            emitter.emit(kind, data)
        else:
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
    # E2: modo máquina. stdout = EXCLUSIVO del stream JSONL; stderr sigue
    # humano. Los exit codes honestos (core/json_events.py) aplican SOLO con
    # --json — el modo humano conserva 0/1/2 (contrato pre-E2 intacto).
    emitter: JsonlEmitter | None = JsonlEmitter() if args.json else None
    # C5 (gemini regla 7): plan-mode y YOLO son mutuamente exclusivos — fail
    # fast al parsear, nunca en caliente.
    if args.plan_mode and "*" in args.approve_tool:
        msg = (
            "tlamati: --plan-mode y --approve-tool '*' son mutuamente exclusivos "
            "(el plan-mode requiere aprobación humana real de los planes)"
        )
        print(msg, file=sys.stderr)
        if emitter is not None:
            emitter.emit_error("args", msg)
        return EXIT_USAGE
    cfg = load_config()
    cfg_provider = cfg.get("provider") or {}
    model = args.model or cfg_provider.get("model") or DEFAULT_MODEL
    base_url = args.base_url or cfg_provider.get("base_url") or DEFAULT_BASE_URL
    api_key = _resolve_api_key(cfg_provider)
    max_turns, stall_repeats = resolve_turn_limits(cfg, args)
    if emitter is not None:
        # Primer evento del stream: qué corrida es esta (consumidor de CI).
        emitter.emit(
            "init",
            {
                "model": model,
                "base_url": base_url,
                "cwd": str(Path.cwd()),
                "max_turns": max_turns,
                "max_context": args.max_context,
                "version": __version__,
            },
        )
    if not api_key:
        msg = "tlamati: falta la API key (OPENROUTER_API_KEY o config provider.api_key_env)"
        print(msg, file=sys.stderr)
        if emitter is not None:
            emitter.emit_error("api_key", msg)
        return EXIT_USAGE

    # C1: session store — persist during the run (crash-safe, ledger lesson).
    store: SessionStore | None = None
    session_id: str | None = None
    resumed_history: list[Any] = []
    if not args.no_session:
        store = SessionStore(args.session_db)
        if store.broken:
            print(f"[session] aviso: {store.broken} — corrida SIN persistir", file=sys.stderr)
            store = None
        else:
            resume_id = args.resume or (store.latest_session_id() if args.continue_last else None)
            if resume_id is not None:
                loaded = store.load_session(resume_id)
                if loaded is None:
                    print(f"[session] no existe la sesión {resume_id!r}", file=sys.stderr)
                    if emitter is not None:
                        emitter.emit_error("session", f"no existe la sesión {resume_id!r}")
                    store.close()
                    return EXIT_USAGE
                session_id = resume_id
                resumed_history = loaded.messages
                print(
                    f"[session] retomando {resume_id} ({len(loaded.messages)} mensajes previos)",
                    file=sys.stderr,
                )
            if session_id is None:
                session_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
                store.create_session(
                    session_id,
                    cwd=str(Path.cwd()),
                    model=model,
                    first_prompt=args.prompt or "",
                )

    provider = OpenAICompat(model=model, base_url=base_url, api_key=api_key)
    sandbox = not args.no_sandbox
    if sandbox and not bwrap_available():
        print(
            "tlamati: bwrap NO instalado — el terminal correrá SIN sandbox "
            "(instalalo con: sudo apt install bubblewrap)",
            file=sys.stderr,
        )
    try:
        policy = Policy(
            PolicyConfig.from_dict(cfg.get("permissions")),
            plan_state=(plan_state := PlanState(active=args.plan_mode)),
        )
    except ValueError as e:
        msg = f"tlamati: configuración de permisos inválida: {e}"
        print(msg, file=sys.stderr)
        if emitter is not None:
            emitter.emit_error("policy", msg)
        return EXIT_USAGE
    ledger: Ledger | None = None
    if not args.no_audit:
        # Merge B5+C1: el ledger reutiliza el session_id del store; sin store
        # (--no-session) genera el suyo con el mismo formato TIMESTAMP-uuid8.
        if session_id is None:
            session_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        db = Path(args.audit_db) if args.audit_db else DEFAULT_AUDIT_DB
        try:
            ledger = Ledger(db, session_id)
        except sqlite3.Error as e:  # auditoría rota no impide correr
            print(
                f"tlamati: ledger de auditoría no disponible ({e}); sigo sin auditoría",
                file=sys.stderr,
            )
    tool_list = make_tools(Path.cwd(), sandbox=sandbox, sandbox_net=args.sandbox_net)

    # C2: durable memory — prefix injection + tools (skipped with --no-memory).
    mem_store: MemoryStore | None = None
    system_prompt = str(cfg.get("system_prompt") or DEFAULT_SYSTEM)

    # Sesión 25 (dogfooding #3): bloque ambiental — el modelo debe saber que
    # SÍ ve el filesystem y dónde están Desktop/Documents REALES (WSL: /mnt).
    # Estático por corrida (cwd+home fijos) → prefijo cacheable byte-estable.
    from tlamati.env_info import environment_block

    system_prompt += "\n\n" + environment_block(Path.cwd())

    # C4: project instructions (AGENTS.md/CLAUDE.md) — outermost first,
    # versioned by content hash so the cacheable prefix is stable.
    if not args.no_instructions:
        instr = load_instructions(Path.cwd())
        if instr.found:
            system_prompt += render_for_prompt(instr)
            print(
                f"[instrucciones] {len(instr.sources)} archivo(s) v:{instr.version}",
                file=sys.stderr,
            )

    # C6: routing.md (workspaces) — AFTER instructions in the prefix (stable
    # order, append-only) and BEFORE volatile blocks (memory/skills), so the
    # cacheable prefix only changes when routing.md or the active context
    # changes. Sin routing.md → prefijo byte-idéntico a pre-C6 (cache sagrada).
    routing = Routing(
        source=None,
        project_root=None,
        workspaces=(),
        active=None,
        table="",
        context_block="",
        version="",
    )
    if not args.no_routing:
        routing = load_routing(Path.cwd(), task=args.prompt, workspace=args.workspace or "")
        if routing.found:
            system_prompt += render_routing_for_prompt(routing)
            active_name = routing.active.name if routing.active else "—"
            print(f"[routing] workspace={active_name} v:{routing.version}", file=sys.stderr)
        if routing.error:
            print(f"[routing] aviso: {routing.error}", file=sys.stderr)

    if not args.no_memory:
        mem_dir = Path(args.memory_dir) if args.memory_dir else default_memory_dir()
        try:
            mem_store = MemoryStore(mem_dir)
            seed_if_empty(mem_store)
            mem_block = mem_store.render_for_prompt()
            if mem_block:
                system_prompt = (
                    system_prompt + "\n\n# MEMORIA DURABLE (leída al inicio; usa el tool `memory` "
                    "para actualizarla)\n" + mem_block
                )
            tool_list.extend(make_memory_tools(mem_store))
        except OSError as e:
            print(f"[memory] aviso: {e} — corrida SIN memoria", file=sys.stderr)
            mem_store = None

    # C3: skills — catalog into prefix, bodies on demand via skill_view.
    if not args.no_memory:
        cfg_skills = cfg.get("skills") or {}
        extra_dirs = [
            Path(os.path.expanduser(str(d)))
            for d in list(args.skills_dir) + list(cfg_skills.get("extra_dirs") or [])
        ]
        try:
            library = SkillLibrary(default_skill_roots(Path.cwd(), extra_dirs))
            # C6: el workspace activo puede cablear skills just-in-time (capa 2).
            # El filtro es por workspace = ESTABLE por corrida (nunca por turno),
            # así el prefijo cacheable no varía entre turnos (regla research/03).
            ws_skills = routing.active.skills if routing.active else ()
            if library.catalog():
                system_prompt = (
                    system_prompt + "\n\n# SKILLS\n" + library.catalog_text(only=ws_skills or None)
                )
            tool_list.extend(make_skill_tools(library))
        except OSError as e:
            print(f"[skills] aviso: {e} — corrida SIN skills", file=sys.stderr)

    # C5+E3c plan-mode: las plan tools SOLO se ofrecen cuando un humano pidió
    # plan-mode explícito (--plan-mode). En headless sin plan-mode, exit_plan_mode
    # es fail-closed por diseño (regla de oro C5: no hay aprobador humano) → la
    # puerta es un callejón sin salida: en la run2 del bench el modelo entró SOLO
    # a plan-mode, quedó encerrado y quemó los 50 turnos (trampa plan-mode,
    # EVALS.md). Fix E3c: no ofrecer una puerta sin salida — el arnés deja de
    # anunciar las tools cuando nadie puede aprobar. Con --plan-mode explícito,
    # exit sigue fail-closed (la regla de oro NO se relaja: solo se retira la
    # oferta, nunca la protección). El bloque de prompt va condicionado con las
    # tools para que el prefijo no mienta; dentro del MISMO modo el prefijo
    # sigue siendo byte-estable (cache sagrada intacta).
    if args.plan_mode:
        system_prompt += PLAN_MODE_PROMPT
        tool_list.extend(make_plan_tools(Path.cwd(), plan_state, plan_approver=None))
    else:
        print(
            "[plan] tools de plan no ofrecidas: corrida headless sin aprobador humano",
            file=sys.stderr,
        )
    # D2 plugins: descubrimiento fail-soft (entry-points + usuario + proyecto +
    # --plugins-dir). NO tocan el prefijo (invisibles al modelo, cache sagrada).
    # El plugin INTERNO de auditoría se registra en el Registry (B5 no opcional).
    # Se crean ANTES del bloque D1: el subagente HEREDA los hooks (la escalera
    # solo endurece — un veto de plugin aplica también dentro del hijo).
    hooks = HookRegistry()
    if not args.no_plugins:
        cfg_plugins = cfg.get("plugins") or {}
        extra_plugin_dirs = [
            Path(os.path.expanduser(str(d)))
            for d in list(args.plugins_dir) + list(cfg_plugins.get("extra_dirs") or [])
        ]
        plugin_report = load_plugins(hooks, project_root=Path.cwd(), extra_dirs=extra_plugin_dirs)
        print(
            f"[plugins] {len(plugin_report.loaded)} cargado(s), "
            f"{len(plugin_report.failed)} fallido(s)",
            file=sys.stderr,
        )

    # D1 subagentes: bloque de prompt ESTÁTICO tras el de plan-mode (prefijo
    # byte-estable) y tool AL FINAL del orden (append-only, cache sagrada).
    # En plan-mode la tool queda DENEGADA sola (fuera de la whitelist C5).
    if not args.no_subagents:
        system_prompt += DELEGATE_PROMPT_BLOCK
        sub_cfg = SubagentConfig.from_dict(cfg.get("subagent"), parent_context=args.max_context)
        # Snapshot ANTES del append: los candidatos del hijo NUNCA incluyen
        # delegate_task (profundidad 1 por construcción, no solo por filtro).
        parent_tools = list(tool_list)
        tool_list.append(
            make_delegate_tool(
                provider,
                tool_candidates=lambda: list(parent_tools),
                config=sub_cfg,
                ledger=ledger,
                hooks=hooks,
            )
        )
    if plan_state.active:
        print(
            "[plan-mode] corrida en PLAN-MODE: escritura/terminal DENEGADAS "
            "hasta aprobar un plan (sin aprobador interactivo, exit falla cerrado)",
            file=sys.stderr,
        )

    # D3 MCP: servidores SOLO declarados en config (--mcp-config override).
    # Tools AL FINAL del tool_list (append-only tras delegate_task, orden
    # estable por (servidor, tool) — cache sagrada). OJO: a diferencia de los
    # plugins D2, las tools MCP SÍ cambian el prefijo (son visibles al modelo):
    # añadir/quitar servidores invalida caché — esperado, es configuración de
    # corrida, estable DENTRO de la corrida. Fail-soft: servidor caído = aviso
    # honesto + corrida sin él. ASK + produces_untrusted innegociables.
    mcp_clients: list[Any] = []
    if not args.no_mcp:
        mcp_cfg: dict[str, Any] = cfg
        if args.mcp_config:
            path = Path(os.path.expanduser(str(args.mcp_config)))
            if path.is_file():
                with open(path) as f:
                    loaded_mcp = yaml.safe_load(f) or {}
                mcp_cfg = loaded_mcp if isinstance(loaded_mcp, dict) else {}
            else:
                print(f"[mcp] aviso: {path} no existe — sin servidores MCP", file=sys.stderr)
                mcp_cfg = {}
        servers, mcp_errors = parse_mcp_config(mcp_cfg.get("mcp"))
        for why in mcp_errors:
            print(f"[mcp] aviso de config: {why}", file=sys.stderr)
        if servers:
            mcp_report = await load_mcp_servers(servers)
            mcp_clients = list(mcp_report.clients)
            tool_list.extend(mcp_report.tools)

    tools = Registry(
        tool_list,
        approver=_headless_approver(args.approve_tool),
        policy=policy,
        ledger=ledger,
        hooks=hooks,
    )
    budget = Budget(max_context_tokens=args.max_context)

    compactor: Compactor | None = None
    summarizer: ModelSummarizer | None = None
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

    run_messages: list[Message] = []

    def _persist(m: Any) -> None:
        run_messages.append(m)
        if store is not None and session_id is not None:
            store.append_message(session_id, m)

    result: LoopResult = await run_loop(
        provider,
        system=system_prompt,
        # Decisión #3 (handoff C5): el ESTADO dinámico viaja en el primer
        # mensaje, nunca en el prefijo (prefijo byte-estable = cache sagrada).
        user_prompt=(
            args.prompt
            if not plan_state.active
            else "[ESTÁS EN PLAN-MODE ACTIVO desde el inicio de esta corrida: "
            "solo exploración y save_plan; escritura/terminal DENEGADAS hasta "
            "que exit_plan_mode sea aprobado.]\n\n" + args.prompt
        ),
        tools=tools,
        budget=budget,
        max_turns=max_turns,
        stall_repeats=stall_repeats,
        on_event=_ledger_wrapper(ledger, args.quiet, emitter),
        compactor=compactor,
        history=resumed_history or None,
        on_message=_persist,
    )

    # D3: cierre limpio de servidores MCP al terminar la corrida (terminate →
    # wait → kill). Un servidor colgado NUNCA cuelga la corrida (nunca raise).
    if mcp_clients:
        await close_mcp(mcp_clients)

    # C2 auto-dream: consolidation AFTER the run, never in the hot turn
    # (CC donor). Uses the cheap summarizer chain; opt-in with --dream.
    if args.dream and mem_store is not None:
        dream_summarizer = summarizer
        if dream_summarizer is None:
            cfg_compact = cfg.get("compaction") or {}
            chain = args.compact_model or cfg_compact.get("model") or DEFAULT_COMPACT_MODEL
            dream_summarizer = ModelSummarizer(
                [
                    OpenAICompat(model=m.strip(), base_url=base_url, api_key=api_key)
                    for m in str(chain).split(",")
                    if m.strip()
                ]
            )
        report = await dream(mem_store, dream_summarizer, run_messages)
        print(report.human(), file=sys.stderr)

    if store is not None and session_id is not None:
        store.record_usage(session_id, result.turns, result.usage)
        store.finish_session(session_id, stop_reason=result.stop_reason, turns=result.turns)
        store.close()
        print(f"[session] {session_id}", file=sys.stderr)
    if emitter is not None:
        # E2: evento terminal SIEMPRE último — el consumidor de CI solo
        # necesita esta línea (+ el exit code del proceso) para decidir.
        emitter.emit("result", result_event(result, session_id=session_id, model=model))
        if emitter.broken:
            print(
                f"[json] aviso: stream roto ({emitter.broken}) — corrida intacta", file=sys.stderr
            )
        u2 = result.usage
        print(
            f"[fin] stop={result.stop_reason} turnos={result.turns} "
            f"tokens: in={u2.input_tokens} out={u2.output_tokens} "
            f"cache_read={u2.cache_read_tokens}",
            file=sys.stderr,
        )
        if result.error:
            print(f"[error] {result.error}", file=sys.stderr)
        if ledger is not None:
            ledger.close()
        return exit_code_for(result.stop_reason)
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


def _run_sessions(args: argparse.Namespace) -> int:
    """`tlamati sessions` — list stored sessions (free, no LLM)."""
    store = SessionStore(args.session_db)
    if store.broken:
        print(f"tlamati: {store.broken}", file=sys.stderr)
        return 2
    sessions = store.list_sessions()
    store.close()
    if not sessions:
        print("(sin sesiones guardadas)")
        return 0
    for s in sessions:
        print(s.human())
    return 0


def _fetch_openrouter_models(base_url: str, api_key: str) -> list[dict[str, Any]]:
    """Lista cruda de modelos del proveedor OpenAI-compatible (fail-loud)."""
    import httpx

    url = base_url.rstrip("/") + "/models"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    resp = httpx.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data if isinstance(data, list) else [])


def _run_model(args: argparse.Namespace) -> int:
    """`tlamati model` — wizard interactivo: proveedor -> modelo -> config.yaml.

    Sin flags, $0, sin LLM. Guarda provider.model/base_url y activa
    models.filter=['*'] para que la paleta /model de la TUI muestre la lista
    remota completa (sin filter, la paleta solo ve el default).
    """
    if not sys.stdin.isatty():
        print(
            "tlamati: `model` es interactivo (necesita terminal). "
            "Alternativa: tlamati --model ID o editar ~/.config/tlamati/config.yaml",
            file=sys.stderr,
        )
        return 2
    cfg = load_config()
    cfg_provider = dict(cfg.get("provider") or {})
    current_model = cfg_provider.get("model") or DEFAULT_MODEL
    current_base = cfg_provider.get("base_url") or DEFAULT_BASE_URL

    print(f"tlamati model — modelo actual: {current_model}")
    print(f"                 base_url actual: {current_base}\n")

    # ---- Paso 1: proveedor ------------------------------------------------
    print("1) PROVEEDOR")
    api_key = _resolve_api_key(cfg_provider)
    key_hint = "key detectada" if api_key else "SIN key"
    options = [
        ("OpenRouter (recomendado — usa tu API key integrada)", DEFAULT_BASE_URL),
        (f"Conservar base_url del config ({current_base})", current_base),
        ("Otro (escribir base_url OpenAI-compatible)", ""),
    ]
    for i, (label, _) in enumerate(options, 1):
        extra = f" — {key_hint}" if i == 1 else ""
        print(f"  {i}. {label}{extra}")
    try:
        choice = input(f"  elige [1-{len(options)}] (Enter = 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n(cancelado)")
        return 1
    if choice == "" or choice == "1":
        base_url = DEFAULT_BASE_URL
    elif choice == "2":
        base_url = current_base
    elif choice == "3":
        base_url = input("  base_url: ").strip() or DEFAULT_BASE_URL
    else:
        print("  opción inválida", file=sys.stderr)
        return 2

    if base_url.rstrip("/") == DEFAULT_BASE_URL.rstrip("/") and not api_key:
        print("  aviso: no hay OPENROUTER_API_KEY ni key en ~/.hermes/.env", file=sys.stderr)

    # ---- Paso 2: modelo ----------------------------------------------------
    print("\n2) MODELO — descargando lista del proveedor...")
    try:
        models = _fetch_openrouter_models(base_url, api_key)
    except Exception as e:  # fail-loud honesto al usuario
        print(
            f"tlamati: no pude traer la lista de modelos ({type(e).__name__}: {e})",
            file=sys.stderr,
        )
        manual = input("  ¿escribir el model id a mano? (Enter = cancelar): ").strip()
        if not manual:
            return 1
        models = [{"id": manual}]

    by_id = {m.get("id", ""): m for m in models}
    print(f"  {len(models)} modelos disponibles.")

    selected: str | None = None
    while selected is None:
        query = input("  busca (Enter = top por contexto, 's' = salir): ").strip().lower()
        if query in ("s", "salir"):
            print("(cancelado)")
            return 1
        if query:
            matches = [m for m in models if query in str(m.get("id", "")).lower()]
            name_q = [
                m for m in models if query in str(m.get("name", "")).lower() and m not in matches
            ]
            matches += name_q
        else:
            matches = sorted(models, key=lambda m: int(m.get("context_length") or 0), reverse=True)[
                :15
            ]
        if not matches:
            print("  sin coincidencias, intenta otro término.")
            continue
        for i, m in enumerate(matches[:20], 1):
            mid = m.get("id", "")
            ctx = m.get("context_length")
            pricing = m.get("pricing") or {}
            prompt_p = pricing.get("prompt")
            try:
                price_str = f"${float(prompt_p) * 1e6:.2f}/M in" if prompt_p is not None else ""
            except (TypeError, ValueError):
                price_str = ""
            ctx_str = f"{ctx // 1000}K ctx" if ctx else ""
            mod = ",".join((m.get("architecture") or {}).get("input_modalities") or [])
            mark = " *" if mid == current_model else ""
            print(f"  {i:2d}. {mid}{mark}  {ctx_str} {price_str} [{mod}]")
        pick = input("  número del modelo (Enter = buscar de nuevo): ").strip()
        if pick == "":
            continue
        try:
            idx = int(pick) - 1
            if 0 <= idx < min(len(matches), 20):
                selected = matches[idx].get("id")
        except ValueError:
            # permite pegar el id completo en vez del número
            if pick in by_id:
                selected = pick
    print(f"\n  elegido: {selected}")

    # ---- Paso 3: guardar config -------------------------------------------
    path = (
        Path(args.config_path)
        if getattr(args, "config_path", None)
        else (Path.home() / ".config" / "tlamati" / "config.yaml")
    )
    cfg["provider"] = {**cfg_provider, "model": selected, "base_url": base_url}
    models_cfg = dict(cfg.get("models") or {})
    filt = models_cfg.get("filter") or []
    if "*" not in [str(p) for p in filt]:
        filt = ["*"] + [str(p) for p in filt]
        models_cfg["filter"] = filt  # paleta /model de la TUI ve todo
    cfg["models"] = models_cfg
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    print(f"  guardado en {path}")
    print(
        "  ✔ próximas corridas (CLI y TUI) usan este modelo; "
        "en la TUI puedes cambiar en vivo con /model"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "audit":
        return _run_audit(args)
    if args.cmd == "sessions":
        return _run_sessions(args)
    if args.cmd == "model":
        return _run_model(args)
    if args.cmd is not None:
        print(
            f"tlamati: subcomando desconocido {args.cmd!r} (existen: sessions, audit, model)",
            file=sys.stderr,
        )
        return 2
    if args.prompt:
        return asyncio.run(_run_headless(args))
    # E1: sin prompt y con terminal INTERACTIVA → la TUI es la cara por
    # defecto (el headless/CI nunca tiene tty → sigue viendo el help y su
    # contrato de exit codes intacto).
    if sys.stdin.isatty() and sys.stdout.isatty():
        from tlamati.tui.app import run_tui  # import perezoso: el extra [tui]

        # E3d PASO A: la TUI recibe --skills-dir igual que headless (antes lo
        # ignoraba — causa madre del dogfooding reprobado, sesión 20).
        skills_extra = [Path(os.path.expanduser(d)) for d in list(args.skills_dir)]
        # E3d PASO B: mismos límites de turnos que headless (pitfall #5).
        tui_max_turns, tui_stall = resolve_turn_limits(load_config(), args)
        return run_tui(
            session_db=args.session_db,
            skills_extra_dirs=skills_extra,
            max_turns=tui_max_turns,
            stall_repeats=tui_stall,
        )
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
