"""The agentic loop — Tlamati's ~500-LOC core (PRD §3 #4).

Shape (GUIA A4): plain async function + state dataclass. No base-class
machinery. while turno → stream → ejecutar tool calls → append → repeat,
hasta stop o presupuesto.

Interjection v1 (donor: grok interjection-core): SIGINT during a turn sets a
pending user message delivered at the START of the next turn; a second SIGINT
aborts. Nothing is ever injected mid-stream (hermes invariant: no synthetic
user messages mid-loop).

Budget (A5 dependency-inversion fix): the loop receives a Budget and asks for
a breakdown BEFORE each provider call; status "exceeded" stops the loop with
an honest result, "warn" is surfaced via the event callback.

Compaction (A6): an optional Compactor is invoked at the budget check, BEFORE
the provider call (message boundary, never mid-stream). It rebuilds the
history SUFFIX only — the cacheable prefix (system, tools, head anchor) is
never mutated ("caching is sacred").
"""

from __future__ import annotations

import asyncio
import json
import signal
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from tlamati.context.budget import Budget
from tlamati.context.compaction import Compactor
from tlamati.core.messages import (
    Message,
    MessageEnd,
    TextDelta,
    ToolCall,
    ToolCallArgsDelta,
    ToolCallStart,
    ToolResult,
    Usage,
)
from tlamati.providers.base import Provider, ProviderError
from tlamati.tools_min.mini import MiniTool, execute


@dataclass
class LoopState:
    """Everything the loop carries across turns."""

    system: str
    history: list[Message] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    turns: int = 0
    pending_interjection: str | None = None


@dataclass(frozen=True)
class LoopResult:
    """Terminal accounting of one run — feeds evals JSONL (A7) and the TUI."""

    final_text: str
    stop_reason: str  # end_turn | max_turns | budget_exceeded | aborted | error | refusal
    turns: int
    usage: Usage
    error: str | None = None


# Loop events for UI consumers (print callback in headless mode).
LoopEvent = Callable[[str, dict[str, Any]], None]


class _Abort(Exception):
    pass


def _install_sigint(
    state: LoopState, abort_flag: dict[str, bool]
) -> Callable[[int, Any], None] | None:
    """SIGINT #1 → pending interjection; SIGINT #2 → abort. Returns the
    previous handler for restore (None if not on main thread/unsupported)."""

    def handler(signum: int, frame: Any) -> None:
        if state.pending_interjection is None and not abort_flag["set"]:
            # First Ctrl-C: queue an interjection the model sees next turn.
            state.pending_interjection = (
                "[INTERRUPCIÓN DEL USUARIO] El usuario presionó Ctrl-C. "
                "Detente y pregunta qué quiere ajustar."
            )
            abort_flag["set"] = True
        else:
            raise _Abort

    try:
        prev = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, handler)
        return prev if callable(prev) else None
    except (ValueError, OSError):
        return None  # not main thread; interjection simply unavailable


async def _stream_one_turn(
    provider: Provider,
    state: LoopState,
    tools: Sequence[MiniTool],
    on_event: LoopEvent,
) -> tuple[Message, MessageEnd | None, str | None]:
    """Consume one provider turn → (assistant Message, MessageEnd, error).

    Assembles streamed deltas into a normalized Message so the history only
    ever contains internal types (invariant: adapters normalize; loop is
    provider-blind)."""
    text_parts: list[str] = []
    tool_starts: dict[str, str] = {}  # id -> name (order preserved)
    tool_args: dict[str, list[str]] = {}  # id -> json fragments
    end: MessageEnd | None = None

    messages = [Message(role="system", content=state.system), *state.history]
    async for ev in provider.stream(messages, [t.as_spec() for t in tools]):
        if isinstance(ev, TextDelta):
            text_parts.append(ev.text)
            on_event("text", {"text": ev.text})
        elif isinstance(ev, ToolCallStart):
            tool_starts[ev.id] = ev.name
            tool_args.setdefault(ev.id, [])
            on_event("tool_start", {"id": ev.id, "name": ev.name})
        elif isinstance(ev, ToolCallArgsDelta):
            tool_args.setdefault(ev.id, []).append(ev.args_json)
        elif isinstance(ev, MessageEnd):
            end = ev

    tool_calls: list[ToolCall] = []
    parse_error: str | None = None
    for tid, name in tool_starts.items():
        raw = "".join(tool_args.get(tid, []))
        try:
            args = json.loads(raw or "{}")
            if not isinstance(args, dict):
                raise ValueError(f"args not an object: {type(args)}")
        except (json.JSONDecodeError, ValueError) as e:
            # Typed degradation: bad args become an ERROR tool result so the
            # model can self-correct, instead of killing the run.
            parse_error = f"tool {name} arguments invalid: {e}; raw={raw[:200]!r}"
            args = {}
        tool_calls.append(ToolCall(id=tid, name=name, arguments=args, raw_arguments=raw))

    # An empty assistant turn (e.g. stream errored with no content) still needs
    # a representable Message — Message forbids empty assistant; use placeholder.
    text = "".join(text_parts)
    assistant = Message(
        role="assistant",
        content=text if (text or tool_calls) else "(sin contenido)",
        tool_calls=tuple(tool_calls),
    )
    return assistant, end, parse_error


async def run_loop(
    provider: Provider,
    *,
    system: str,
    user_prompt: str,
    tools: Sequence[MiniTool],
    budget: Budget,
    max_turns: int = 20,
    on_event: LoopEvent | None = None,
    compactor: Compactor | None = None,
) -> LoopResult:
    """Run the agent until end_turn, budget, max_turns, abort, or error."""
    noop: LoopEvent = lambda kind, data: None  # noqa: E731
    on_event = on_event or noop
    state = LoopState(system=system)
    state.history.append(Message(role="user", content=user_prompt))
    abort_flag = {"set": False}
    prev_handler = _install_sigint(state, abort_flag)
    tool_by_name = {t.name: t for t in tools}

    try:
        return await _run_inner(
            provider, state, tools, tool_by_name, budget, max_turns, on_event, compactor
        )
    except _Abort:
        return LoopResult(
            final_text="(ejecución abortada por el usuario)",
            stop_reason="aborted",
            turns=state.turns,
            usage=state.usage,
        )
    except ProviderError as e:
        return LoopResult(
            final_text="",
            stop_reason="error",
            turns=state.turns,
            usage=state.usage,
            error=f"{e.kind}: {e}",
        )
    finally:
        if prev_handler is not None:
            signal.signal(signal.SIGINT, prev_handler)


async def _run_inner(
    provider: Provider,
    state: LoopState,
    tools: Sequence[MiniTool],
    tool_by_name: dict[str, MiniTool],
    budget: Budget,
    max_turns: int,
    on_event: LoopEvent,
    compactor: Compactor | None = None,
) -> LoopResult:
    last_text = ""
    tool_specs = [t.as_spec() for t in tools]
    while state.turns < max_turns:
        # Interjection v1: pending user message enters at turn start.
        if state.pending_interjection:
            state.history.append(Message(role="user", content=state.pending_interjection))
            state.pending_interjection = None

        # Budget check BEFORE spending (A5 inversion fix).
        breakdown = budget.breakdown(state.system, tool_specs, state.history)
        on_event("budget", {"breakdown": breakdown.human()})
        if compactor is not None and breakdown.status != "ok":
            # A6: compact the SUFFIX only, at a message boundary (golden rule:
            # never mutate the cacheable prefix; never mid-stream).
            state.history, report = await compactor.compact(
                state.history,
                system=state.system,
                tools=tool_specs,
                budget=budget,
                status=breakdown.status,
            )
            if report is not None:
                state.usage = state.usage + report.usage
                on_event(
                    "compaction",
                    {
                        "microcompacted": report.microcompacted,
                        "summarized": report.summarized,
                        "summary_failed": report.summary_failed,
                        "tokens_before": report.tokens_before,
                        "tokens_after": report.tokens_after,
                    },
                )
                breakdown = budget.breakdown(state.system, tool_specs, state.history)
        if breakdown.status == "exceeded":
            return LoopResult(
                final_text=last_text,
                stop_reason="budget_exceeded",
                turns=state.turns,
                usage=state.usage,
                error=breakdown.human(),
            )

        assistant, end, parse_error = await _stream_one_turn(provider, state, tools, on_event)
        state.turns += 1
        state.history.append(assistant)
        if end is not None:
            state.usage = state.usage + end.usage
        on_event("turn_end", {"turn": state.turns, "usage": end.usage if end else Usage()})

        if assistant.content:
            last_text = assistant.content

        if end is None or end.stop_reason == "error":
            err = (end.error if end else "stream ended without MessageEnd") or parse_error
            return LoopResult(
                final_text=last_text,
                stop_reason="error",
                turns=state.turns,
                usage=state.usage,
                error=err,
            )
        if end.stop_reason == "refusal":
            return LoopResult(
                final_text=last_text,
                stop_reason="refusal",
                turns=state.turns,
                usage=state.usage,
            )
        if end.stop_reason == "max_tokens" and not assistant.tool_calls:
            return LoopResult(
                final_text=last_text,
                stop_reason="max_tokens",
                turns=state.turns,
                usage=state.usage,
            )

        if not assistant.tool_calls:
            return LoopResult(
                final_text=last_text,
                stop_reason="end_turn",
                turns=state.turns,
                usage=state.usage,
            )

        # Execute tools sequentially (deterministic, audit-friendly).
        for tc in assistant.tool_calls:
            if parse_error and not tc.arguments and tc.raw_arguments:
                result = ToolResult(
                    tool_call_id=tc.id, content=f"ERROR: {parse_error}", is_error=True
                )
            else:
                tool = tool_by_name.get(tc.name)
                if tool is None:
                    result = ToolResult(
                        tool_call_id=tc.id,
                        content=f"ERROR: unknown tool {tc.name!r}",
                        is_error=True,
                    )
                else:
                    on_event("tool_run", {"name": tc.name, "args": tc.arguments})
                    result = await execute(tool, tc.arguments, tc.id)
            on_event("tool_result", {"id": tc.id, "is_error": result.is_error})
            state.history.append(Message(role="tool", tool_result=result))

        await asyncio.sleep(0)  # yield to event loop (signal delivery)

    return LoopResult(
        final_text=last_text,
        stop_reason="max_turns",
        turns=state.turns,
        usage=state.usage,
    )
