"""CLI entry point. Fase A: --version + stub for -p (wired in A4)."""

from __future__ import annotations

import argparse
import sys

from tlamati import __version__


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
        help="Headless one-shot prompt (full agent loop arrives in A4)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.prompt:
        # Placeholder hasta A4: honest exit, no fake success.
        print("tlamati: agent loop not implemented yet (llega en A4)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
