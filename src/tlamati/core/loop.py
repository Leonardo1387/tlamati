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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tlamati.context.budget import Budget
from tlamati.context.compaction import Compactor
from tlamati.core.images import ImageBlock
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
from tlamati.tools.registry import Registry


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
    stop_reason: str  # end_turn | max_turns | stall | budget_exceeded | aborted | error | refusal
    turns: int
    usage: Usage
    error: str | None = None


# Loop events for UI consumers (print callback in headless mode).
LoopEvent = Callable[[str, dict[str, Any]], None]


class _Abort(Exception):
    """Corte por usuario (SIGINT x2 o control.abort). Carga el texto parcial."""

    def __init__(self, final_text: str = "") -> None:
        super().__init__(final_text)
        self.final_text = final_text


@dataclass
class LoopControl:
    """Canal de control UI→loop (B3/B4, dogfood #9).

    La TUI corre el terminal en modo raw: Ctrl+C NUNCA llega como SIGINT, así
    que el handler de señal es código muerto ahí. LoopControl es el equivalente
    portable: la UI muta estos campos desde su propio event loop (mismo hilo
    asyncio que run_loop — sin locks) y el loop los lee en fronteras seguras:
    - ``abort``: corte inmediato (se chequea entre deltas del stream, antes de
      cada tool call y al inicio de turno) → stop_reason="aborted".
    - ``pending_interjection``: mensaje del usuario escrito A MITAD de turno;
      entra como user message al INICIO del siguiente turno (invariante hermes:
      nunca se inyecta mid-stream). SIGINT y LoopControl comparten el campo de
      LoopState — una sola vía de entrega.
    """

    abort: bool = False
    pending_interjection: str | None = None


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
    tools: Registry,
    on_event: LoopEvent,
    control: LoopControl | None = None,
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
    async for ev in provider.stream(messages, tools.specs()):
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
        # B3: abort entre deltas — corte a media generación, sin esperar al
        # fin del stream. Va DESPUÉS de procesar el evento: el delta que ya
        # llegó es texto parcial rescatable, no se tira.
        if control is not None and control.abort:
            raise _Abort("".join(text_parts))

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
    tools: Registry,
    budget: Budget,
    max_turns: int = 60,
    stall_repeats: int = 3,
    on_event: LoopEvent | None = None,
    compactor: Compactor | None = None,
    history: list[Message] | None = None,
    on_message: Callable[[Message], None] | None = None,
    control: LoopControl | None = None,
    user_images: tuple[ImageBlock, ...] = (),
) -> LoopResult:
    """Run the agent until end_turn, budget, max_turns, stall, abort, or error.

    E3d PASO B (diseño del fundador): max_turns <= 0 = "yolo" (sin muro global;
    el presupuesto de contexto sigue siendo el techo sagrado). El detector de
    estancamiento es INDEPENDIENTE: misma herramienta + mismos argumentos
    ``stall_repeats`` turnos seguidos = bucle muerto → corte duro con
    stop_reason="stall" (0 lo desactiva).

    C1 (session store): ``history`` seeds a RESUMED conversation (messages are
    replayed as-is; the loop stays provider-blind). ``on_message`` is called
    for every message appended (user prompt, assistant turns, tool results)
    so the caller can persist DURING the run — a crashed run keeps everything
    written up to the crash (same robustness lesson as the B5 ledger).
    """
    noop: LoopEvent = lambda kind, data: None  # noqa: E731
    on_event = on_event or noop
    state = LoopState(system=system)
    if history:
        state.history.extend(history)
    # Vision v2.1: las imágenes del usuario viajan NATIVAS en el primer
    # mensaje; sus markers de texto se adjuntan al content para que la sesión
    # persistida (que guarda metadata, no píxeles) conserve el registro de
    # qué se mostró.
    prompt_text = user_prompt
    if user_images:
        markers = "\n".join(im.marker() for im in user_images)
        prompt_text = f"{user_prompt}\n{markers}" if user_prompt else markers
    first = Message(role="user", content=prompt_text, images=user_images)
    state.history.append(first)
    if on_message is not None:
        on_message(first)
    abort_flag = {"set": False}
    prev_handler = _install_sigint(state, abort_flag)

    try:
        return await _run_inner(
            provider,
            state,
            tools,
            budget,
            max_turns,
            on_event,
            compactor,
            on_message,
            stall_repeats=stall_repeats,
            control=control,
        )
    except _Abort as ab:
        return LoopResult(
            final_text=ab.final_text or "(ejecución abortada por el usuario)",
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


def _calls_signature(assistant: Message) -> str | None:
    """Firma de avance del turno: herramientas + argumentos exactos (json
    canónico). Sin tool calls = None (el turno de texto nunca "repite").
    Editar el mismo archivo con contenido DISTINTO cambia la firma → no cuenta
    como bucle; reintentar lo IDÉNTICO esperando otro resultado, sí."""
    if not assistant.tool_calls:
        return None
    return json.dumps(
        [(tc.name, tc.arguments) for tc in assistant.tool_calls],
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


async def _run_inner(
    provider: Provider,
    state: LoopState,
    tools: Registry,
    budget: Budget,
    max_turns: int,
    on_event: LoopEvent,
    compactor: Compactor | None = None,
    on_message: Callable[[Message], None] | None = None,
    *,
    stall_repeats: int = 3,
    control: LoopControl | None = None,
) -> LoopResult:
    last_text = ""
    tool_specs = tools.specs()
    # Detector de estancamiento (E3d PASO B, diseño del fundador): la misma
    # firma de tool calls N turnos seguidos = bucle muerto → corte duro y
    # AVISO explícito (nada de loops interminables en silencio). stall_repeats
    # <= 0 desactiva el detector.
    prev_signature: str | None = None
    repeat_count = 0
    while max_turns <= 0 or state.turns < max_turns:
        # B4: la UI encola steering por LoopControl (la TUI nunca ve SIGINT —
        # modo raw). Se drena hacia el mismo canal que SIGINT: una sola vía.
        if control is not None:
            if control.abort:
                raise _Abort(last_text)
            if control.pending_interjection and state.pending_interjection is None:
                state.pending_interjection = control.pending_interjection
                control.pending_interjection = None
        # Interjection v1: pending user message enters at turn start.
        if state.pending_interjection:
            interj = Message(role="user", content=state.pending_interjection)
            state.history.append(interj)
            if on_message is not None:
                on_message(interj)
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

        assistant, end, parse_error = await _stream_one_turn(
            provider, state, tools, on_event, control
        )
        state.turns += 1
        state.history.append(assistant)
        if on_message is not None:
            on_message(assistant)
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
            # B4 (steering Hermes): si el usuario escribió a mitad de turno y
            # el modelo ya cerró, el mensaje NO se pierde — entra como user
            # message y el loop sigue un turno más.
            steer = None
            if control is not None and control.pending_interjection:
                steer = control.pending_interjection
                control.pending_interjection = None
            if steer:
                steer_msg = Message(role="user", content=steer)
                state.history.append(steer_msg)
                if on_message is not None:
                    on_message(steer_msg)
                on_event("steering", {"text": steer})
                continue
            return LoopResult(
                final_text=last_text,
                stop_reason="end_turn",
                turns=state.turns,
                usage=state.usage,
            )

        # Execute tools sequentially (deterministic, audit-friendly).
        for tc in assistant.tool_calls:
            if control is not None and control.abort:
                raise _Abort(assistant.content or last_text)
            if parse_error and not tc.arguments and tc.raw_arguments:
                result = ToolResult(
                    tool_call_id=tc.id, content=f"ERROR: {parse_error}", is_error=True
                )
            else:
                # Registry guards: unknown tool → schema → permission → run.
                on_event("tool_run", {"name": tc.name, "args": tc.arguments})
                result = await tools.execute(tc.name, tc.arguments, tc.id)
            on_event("tool_result", {"id": tc.id, "is_error": result.is_error})
            tool_msg = Message(role="tool", tool_result=result)
            state.history.append(tool_msg)
            if on_message is not None:
                on_message(tool_msg)

        # Detector de estancamiento: firma idéntica N turnos seguidos = corte.
        if stall_repeats > 0 and assistant.tool_calls:
            signature = _calls_signature(assistant)
            if signature == prev_signature:
                repeat_count += 1
            else:
                repeat_count = 1
            prev_signature = signature
            if repeat_count >= stall_repeats:
                nombres = ", ".join(sorted({tc.name for tc in assistant.tool_calls}))
                msg = (
                    f"bucle detectado: {repeat_count} turnos seguidos llamando "
                    f"{nombres} con los MISMOS argumentos, sin avance. "
                    "Corrida detenida (stop_reason=stall)."
                )
                on_event("stall", {"repeats": repeat_count, "tools": nombres})
                return LoopResult(
                    final_text=last_text,
                    stop_reason="stall",
                    turns=state.turns,
                    usage=state.usage,
                    error=msg,
                )
        elif stall_repeats > 0:
            prev_signature = None
            repeat_count = 0

        await asyncio.sleep(0)  # yield to event loop (signal delivery)

    return LoopResult(
        final_text=last_text,
        stop_reason="max_turns",
        turns=state.turns,
        usage=state.usage,
    )
