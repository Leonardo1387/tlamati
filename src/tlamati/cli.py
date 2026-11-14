"""CLI entry point.

Fase A: headless one-shot `tlamati -p "..."` contra OpenRouter (config.yaml o
defaults + OPENROUTER_API_KEY). TUI Textual llega en Fase E.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from tlamati import __version__
from tlamati.context.budget import Budget
from tlamati.core.loop import LoopResult, run_loop
from tlamati.providers.openai_compat import OpenAICompat
from tlamati.tools_min.mini import make_tools

DEFAULT_SYSTEM = (
    "Eres Tlamati, un agente de terminal local-first. Resuelve la tarea con las "
    "herramientas disponibles. Sé breve y directo. Trabaja en el directorio actual. "
    "Cuando termines, di TERMINADO y resume qué cambiaste."
)
DEFAULT_MODEL = "qwen/qwen3-coder"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MAX_CONTEXT = 128_000

CONFIG_PATHS = (
    Path("tlamati.yaml"),
    Path.home() / ".config" / "tlamati" / "config.yaml",
)


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
    p.add_argument("--quiet", action="store_true", help="suppress streaming output")
    return p


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
    tools = make_tools(Path.cwd())
    budget = Budget(max_context_tokens=args.max_context)

    result: LoopResult = await run_loop(
        provider,
        system=cfg.get("system_prompt") or DEFAULT_SYSTEM,
        user_prompt=args.prompt,
        tools=tools,
        budget=budget,
        max_turns=args.max_turns,
        on_event=_printer(args.quiet),
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
    return 0 if result.stop_reason in ("end_turn",) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.prompt:
        return asyncio.run(_run_headless(args))
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
