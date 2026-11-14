"""Internal message types — the narrow waist of Tlamati.

Every provider adapter translates to/from these types and NOTHING else.
Invariant (PRD §7): any provider call normalizes tool_calls into this internal
format, or degrades with a declared fallback.

Design notes:
- Frozen dataclasses, stdlib only: the core must stay dependency-free and
  hashable/comparable for cheap snapshot tests.
- ``Usage`` is additive so per-turn and per-session ledgers can sum it.
- Stream events (bottom of file) are what ``providers`` emit; the loop is the
  only consumer.

Marked STABLE (Han-Lee test: a better model does not invalidate these types).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{time.time_ns():x}"


@dataclass(frozen=True)
class ToolCall:
    """A model's request to invoke a tool, normalized to internal form.

    ``arguments`` is the parsed dict; ``raw_arguments`` keeps the verbatim
    string the provider streamed (needed for audit ledger + for re-serializing
    byte-stably when the provider round-trips it).
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str = ""


@dataclass(frozen=True)
class ToolResult:
    """Result of executing a ToolCall, normalized.

    ``untrusted`` marks content that crossed in from outside (web fetches,
    MCP servers, file reads of non-owned paths). The lethal-trifecta policy
    (Fase B) escalates outbound tools to "ask" when the turn consumed any
    untrusted result.
    ``truncated`` is the honest marker for spout-level truncation (M1).
    """

    tool_call_id: str
    content: str
    is_error: bool = False
    untrusted: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class Message:
    """One conversation message.

    Shape rules (mirrors both Anthropic and OpenAI semantics so adapters stay
    thin):
    - role="assistant" may carry ``tool_calls`` (content may be empty).
    - role="tool" carries exactly one ``tool_result``.
    - role="system" is reserved for the cacheable prefix builder.
    """

    role: Role
    content: str = ""
    id: str = field(default_factory=lambda: _new_id("msg"))
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None

    def __post_init__(self) -> None:
        if self.role == "assistant" and not self.content and not self.tool_calls:
            raise ValueError("assistant message must carry content or tool_calls")
        if self.role == "tool" and self.tool_result is None:
            raise ValueError("tool message must carry a tool_result")

    # -- serialization (sessions SQLite + evals JSONL) -------------------

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content, "id": self.id}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "raw_arguments": tc.raw_arguments,
                }
                for tc in self.tool_calls
            ]
        if self.tool_result is not None:
            tr = self.tool_result
            d["tool_result"] = {
                "tool_call_id": tr.tool_call_id,
                "content": tr.content,
                "is_error": tr.is_error,
                "untrusted": tr.untrusted,
                "truncated": tr.truncated,
            }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        tool_calls = tuple(
            ToolCall(
                id=tc["id"],
                name=tc["name"],
                arguments=tc.get("arguments", {}),
                raw_arguments=tc.get("raw_arguments", ""),
            )
            for tc in d.get("tool_calls", ())
        )
        tr_d = d.get("tool_result")
        tool_result = (
            ToolResult(
                tool_call_id=tr_d["tool_call_id"],
                content=tr_d["content"],
                is_error=tr_d.get("is_error", False),
                untrusted=tr_d.get("untrusted", False),
                truncated=tr_d.get("truncated", False),
            )
            if tr_d is not None
            else None
        )
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            id=d.get("id") or _new_id("msg"),
            tool_calls=tool_calls,
            tool_result=tool_result,
        )


@dataclass(frozen=True)
class Usage:
    """Token/cost accounting for one provider call. Additive across turns.

    Cache fields exist from day one so the "cacheable prefix" invariant is
    MEASURABLE (PRD §5: cost visible per turn; research/05: overhead <8k).
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None

    def __add__(self, other: Usage) -> Usage:
        cost = None
        if self.cost_usd is not None or other.cost_usd is not None:
            cost = (self.cost_usd or 0.0) + (other.cost_usd or 0.0)
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            cost_usd=cost,
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ---------------------------------------------------------------------------
# Stream events — the ONLY vocabulary between providers/ and core/loop.py.
# Adapters translate their native SSE chunks into these; the loop never sees
# provider-specific shapes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextDelta:
    """A streamed chunk of assistant text."""

    text: str


@dataclass(frozen=True)
class ToolCallStart:
    """Provider signalled a new tool call (id known, args still streaming)."""

    id: str
    name: str


@dataclass(frozen=True)
class ToolCallArgsDelta:
    """A streamed chunk of JSON arguments for the current tool call."""

    id: str
    args_json: str


@dataclass(frozen=True)
class MessageEnd:
    """Terminal event of one assistant turn.

    ``stop_reason`` normalized vocabulary:
      "end_turn"      — model finished normally
      "tool_use"      — model stopped to await tool results
      "max_tokens"    — hit output cap (loop may continue or surface error)
      "refusal"       — provider flagged a refusal (mapped to typed error)
      "error"         — provider/stream error; ``error`` carries detail
    Anything the provider emits that we don't recognize MUST map to "error"
    with the raw value preserved — never silently dropped (GUIA A3 test).
    """

    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "refusal", "error"]
    usage: Usage = field(default_factory=Usage)
    error: str | None = None


Event = TextDelta | ToolCallStart | ToolCallArgsDelta | MessageEnd
