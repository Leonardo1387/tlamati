"""Context budget — token counting, thresholds, and VISIBLE per-section breakdown.

Meta-lesson from research/05 (Claude Code's prompt builder): every section of
the prefix is NAMED, TOGGLEABLE, and its cost is VISIBLE. PRD §5: overhead
pre-primer-prompt < 8k tokens — that is only enforceable if we measure it.

Counting strategy (GUIA A5): tiktoken (cl100k_base) when available, honest
approximator (chars/4) otherwise — never a silent zero.

Thresholds: 80% warn, 95% exceeded (donor: codex compact_token_budget.rs).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from tlamati.core.messages import Message
from tlamati.providers.base import ToolSpec

BudgetStatus = Literal["ok", "warn", "exceeded"]

WARN_RATIO = 0.80
HARD_RATIO = 0.95


@lru_cache(maxsize=1)
def _encoding() -> object | None:
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - tiktoken es dependencia declarada
        return None


def count_tokens(text: str) -> int:
    """Token count with honest fallback: exact-ish via cl100k_base, else
    chars/4 approximator. Never raises, never returns 0 for non-empty text."""
    if not text:
        return 0
    enc = _encoding()
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))  # type: ignore[attr-defined]
        except Exception:
            pass
    return max(1, len(text) // 4)


def _message_tokens(m: Message) -> int:
    total = count_tokens(m.content)
    for tc in m.tool_calls:
        total += count_tokens(tc.name) + count_tokens(tc.raw_arguments or json.dumps(tc.arguments))
    if m.tool_result is not None:
        total += count_tokens(m.tool_result.content)
        # Vision v2.1: los píxeles cuestan (w*h/750 en Anthropic); ignorarlos
        # haría mentir al budget justo cuando más caro es el turno.
        total += sum(im.token_estimate() for im in m.tool_result.images)
    total += sum(im.token_estimate() for im in m.images)
    return total + 4  # per-message protocol overhead estimate


@dataclass(frozen=True)
class SectionCost:
    """One named, toggleable section of the context (CC registry pattern)."""

    name: str
    tokens: int
    enabled: bool = True


@dataclass(frozen=True)
class ContextBreakdown:
    """Full accounting of what the next provider call would carry."""

    sections: tuple[SectionCost, ...]
    max_context_tokens: int

    @property
    def total(self) -> int:
        return sum(s.tokens for s in self.sections if s.enabled)

    @property
    def status(self) -> BudgetStatus:
        if self.max_context_tokens <= 0:
            return "exceeded"
        ratio = self.total / self.max_context_tokens
        if ratio >= HARD_RATIO:
            return "exceeded"
        if ratio >= WARN_RATIO:
            return "warn"
        return "ok"

    def human(self) -> str:
        parts = [f"{s.name}={s.tokens}" for s in self.sections if s.enabled]
        pct = (
            f"{100 * self.total / self.max_context_tokens:.0f}%" if self.max_context_tokens else "?"
        )
        return (
            f"ctx: {' '.join(parts)} total={self.total} "
            f"({pct} de {self.max_context_tokens}) [{self.status}]"
        )


class Budget:
    """Token budget for one conversation. Stateless per call: the breakdown is
    recomputed from the live message list (no drift between counted and real)."""

    def __init__(self, max_context_tokens: int) -> None:
        self.max_context_tokens = max_context_tokens

    def breakdown(
        self,
        system: str,
        tools: Sequence[ToolSpec],
        history: Sequence[Message],
    ) -> ContextBreakdown:
        tools_tokens = 0
        for t in tools:
            tools_tokens += (
                count_tokens(t.name)
                + count_tokens(t.description)
                + count_tokens(json.dumps(t.input_schema))
            )
        history_tokens = sum(_message_tokens(m) for m in history)
        sections = (
            SectionCost("system", count_tokens(system)),
            SectionCost("tools", tools_tokens),
            SectionCost("history", history_tokens),
        )
        return ContextBreakdown(sections=sections, max_context_tokens=self.max_context_tokens)
