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
import random
import re
import signal
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Literal

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
    """Everything the loop carries across turns.

    T2: ``history_seqs`` es la lista paralela posición→seq de DB de
    ``history`` (None = mensaje que no vive en la tabla messages, p.ej. el
    marker de resumen). Viaja con la history para que una compactación pueda
    traducir posiciones a rangos de seq persistidos (record_summary).
    """

    system: str
    history: list[Message] = field(default_factory=list)
    history_seqs: list[int | None] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    turns: int = 0
    pending_interjection: str | None = None
    # T1 (cuasi-stall): ventana deslizante de firmas NORMALIZADAS de las
    # últimas llamadas a tools (runtime puro; no se persiste).
    quasi_window: deque[str] = field(default_factory=deque)
    quasi_last_warned: int = 0


@dataclass(frozen=True)
class LoopResult:
    """Terminal accounting of one run — feeds evals JSONL (A7) and the TUI.

    T2: ``history`` trae la history FINAL (post-compactación) para que el
    consumidor multi-turno (TUI) re-siembre la siguiente corrida con el
    contexto compactado en vez de la historia cruda completa.
    ``history_seqs`` es la lista paralela posición→seq de DB (None = mensaje
    que NO vive en la tabla messages, p.ej. el marker de resumen: su contenido
    se persiste en la tabla summaries vía record_summary).
    """

    final_text: str
    stop_reason: str  # end_turn | max_turns | stall | budget_exceeded | aborted | error | refusal
    turns: int
    usage: Usage
    error: str | None = None
    history: list[Message] = field(default_factory=list)
    history_seqs: list[int | None] = field(default_factory=list)


# Loop events for UI consumers (print callback in headless mode).
LoopEvent = Callable[[str, dict[str, Any]], None]

# T2: persistencia de compactación. ``on_message`` devuelve el seq de DB que
# el store asignó al mensaje (None si no se persiste / store roto); el loop lo
# usa para mantener ``history_seqs`` alineada posición a posición. ``on_summary``
# recibe (from_seq, to_seq, texto del marker) cuando una compactación reemplaza
# un rango de mensajes crudos por un resumen — el llamador lo persiste con
# store.record_summary (append-only: los crudos NUNCA se borran).
MessageSink = Callable[[Message], "int | None"]
SummarySink = Callable[[int, int, str], None]

# Retry de errores transitorios del proveedor (rate limit Alibaba vía
# OpenRouter, 26-nov). Backoff exponencial 4s·2^n + jitter, 4 reintentos
# (4+8+16+32 ≈ 60s de ventana) — suficiente para que un bucket de rate
# limit se recupere sin duplicar gasto en errores deterministas.
_MAX_PROVIDER_RETRIES = 4
_RETRY_BASE_S = 4.0

# Patrones de error TRANSITORIO en el mensaje de MessageEnd(error). Los
# gateways (OpenRouter) a veces entregan HTTP 200 + cuerpo de error SSE:
# en ese camino no hay status code, solo texto. Mayúsculas/minúsculas no
# importan; coincidencia de subcadena.
_TRANSIENT_PATTERNS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "overloaded",
    "capacity",
    "temporarily unavailable",
    "in-flight",
    "please slow down",
    "retry after",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "502 bad gateway",
    "503 service",
    "504 gateway",
    "upstream error",
    "model serving",
    "connection reset",
    "timed out",
    "timeout",
)


# T1 — Detector de cuasi-stall (dogfood 27-nov: el detector exacto nunca
# cortó una sesión real — 0 rachas de ≥3 idénticas consecutivas en las
# sesiones de 332/433 turnos — pero el 43% de las llamadas terminal
# repitieron el mismo prefijo-80 en ventana de 20: el bucle real es
# CUASI-repetitivo, mutando timeouts/flags/rutas). Decisiones del fundador
# (YA TOMADAS): similitud ≥85% (las mutaciones reales mueven 10-15% del
# texto), ventana 15, ≥5 → aviso SOFT inyectado al modelo, ≥8 → ASK al
# usuario (seguir/redirigir/parar). NUNCA corte duro por cuasi-similitud:
# el corte duro por firma EXACTA consecutiva (stall_repeats) se queda solo.
QuasiAskDecision = Literal["seguir", "redirigir", "parar"]
QUASI_ASK_OPTIONS: tuple[str, ...] = ("seguir", "redirigir", "parar")
# La TUI pasa un handler async (matches:int)->QuasiAskDecision que muestra
# el diálogo; headless sin handler = degradación honesta a stop_reason stall.
QuasiAskHandler = Callable[[int], Any]

# Dígitos a placeholder: timeouts/sleeps/puertos/contadores mutados son la
# variación típica del bucle cuasi-repetitivo (timeout 90→110, intento 3→4).
_DIGITS_RE = re.compile(r"\d+")
_WS_RE = re.compile(r"\s+")


def _quasi_signature(calls: tuple[ToolCall, ...]) -> str | None:
    """Firma NORMALIZADA de los tool calls del turno (T1).

    Misma base que _calls_signature (json canónico de (name, args)) colapsada
    para similitud: whitespace → espacio único y dígitos → '#'. Sin tool
    calls = None (los turnos de texto nunca "repiten")."""
    if not calls:
        return None
    raw = json.dumps(
        [(tc.name, tc.arguments) for tc in calls],
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return _WS_RE.sub(" ", _DIGITS_RE.sub("#", raw))


def _quasi_count(signature: str, window: deque[str], threshold: float) -> int:
    """Cuántas firmas de la ventana son cuasi-idénticas (ratio ≥ threshold)."""
    return sum(1 for prev in window if SequenceMatcher(None, prev, signature).ratio() >= threshold)


QUASI_WARN_TEMPLATE = (
    "[AVISO DE ESTANCAMIENTO CUASI-REPETITIVO] Llevas {n} llamadas "
    "cuasi-idénticas (similitud ≥{pct}%) en las últimas {w}. Cambia de "
    "estrategia: si el comando falla, diagnostica la causa raíz en vez de "
    "reintentar con variaciones menores; si esperas un estado externo, dilo "
    "explícitamente y pregunta al usuario."
)


@dataclass(frozen=True)
class QuasiStallConfig:
    """Knobs del detector de cuasi-stall (T1). Defaults = decisión del fundador.

    ``similarity`` a 0 (o ``window``/``warn_count`` ≤ 0) desactiva el detector
    por completo. El corte duro de firma EXACTA (``stall_repeats`` de run_loop)
    es ortogonal y sigue operando independiente de esta config.
    """

    similarity: float = 0.85
    window: int = 15
    warn_count: int = 5
    ask_count: int = 8

    @property
    def enabled(self) -> bool:
        return self.similarity > 0 and self.window > 0 and self.warn_count > 0


def _is_transient_error(message: str | None) -> bool:
    if not message:
        return False
    low = message.lower()
    return any(p in low for p in _TRANSIENT_PATTERNS)


class _TurnRetryable(Exception):
    """Error transitorio detectado al FINAL del stream (MessageEnd error).
    Carga el resultado parcial para devolverlo si se agotan los reintentos."""

    def __init__(
        self,
        result: tuple[Message, MessageEnd | None, str | None],
        reason: str,
    ) -> None:
        super().__init__(reason)
        self.result = result
        self.reason = reason


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
    provider-blind).

    Retry con backoff exponencial (fix rate-limit Alibaba 26-nov): reintenta
    el turno COMPLETO cuando (a) el provider lanza ProviderError(retryable)
    — HTTP 429/5xx/transporte — o (b) el stream termina en
    MessageEnd(stop_reason="error") con un mensaje que matchea patrones
    transitorios (rate limit, overloaded, upstream 429/5xx, in-flight
    credits). Los errores deterministas (refusal, finish_reason desconocido,
    argumentos inválidos) NO se reintentan: reintentar lo idéntico esperando
    otro resultado es el bucle que el detector de estancamiento prohíbe.
    """
    last_error: str | None = None
    for attempt in range(_MAX_PROVIDER_RETRIES + 1):
        if attempt > 0:
            delay = _RETRY_BASE_S * (2 ** (attempt - 1)) + random.uniform(0, 1.0)
            on_event(
                "retry",
                {
                    "attempt": attempt,
                    "max_attempts": _MAX_PROVIDER_RETRIES,
                    "delay_s": round(delay, 1),
                    "error": (last_error or "")[:300],
                },
            )
            if control is not None and control.abort:
                raise _Abort("")
            await asyncio.sleep(delay)
        try:
            return await _consume_turn(provider, state, tools, on_event, control)
        except ProviderError as e:
            if not e.retryable or attempt >= _MAX_PROVIDER_RETRIES:
                raise
            last_error = f"{e.kind}: {e}"
        except _TurnRetryable as tr:
            # Error transitorio detectado en el MessageEnd (HTTP 200 + body
            # de error, patrón OpenRouter/Alibaba). Reintento completo.
            if attempt >= _MAX_PROVIDER_RETRIES:
                return tr.result
            last_error = tr.reason
    raise AssertionError("unreachable: retry loop must return or raise")


async def _consume_turn(
    provider: Provider,
    state: LoopState,
    tools: Registry,
    on_event: LoopEvent,
    control: LoopControl | None = None,
) -> tuple[Message, MessageEnd | None, str | None]:
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
    result = (assistant, end, parse_error)
    # Error transitorio al final del stream (HTTP 200 + error body, o SSE que
    # mapeó a stop_reason="error" con mensaje de rate limit/overload): se
    # señala hacia _stream_one_turn para backoff+reintento. Si no matchea,
    # el resultado vuelve tal cual (error determinista → loop decide).
    if end is not None and end.stop_reason == "error" and _is_transient_error(end.error):
        raise _TurnRetryable(result, end.error or "transient provider error")
    return result


async def run_loop(
    provider: Provider,
    *,
    system: str,
    user_prompt: str,
    tools: Registry,
    budget: Budget,
    max_turns: int = 60,
    stall_repeats: int = 3,
    quasi_stall: QuasiStallConfig | None = None,
    quasi_ask: QuasiAskHandler | None = None,
    on_event: LoopEvent | None = None,
    compactor: Compactor | None = None,
    history: list[Message] | None = None,
    history_seqs: list[int | None] | None = None,
    on_message: MessageSink | None = None,
    on_summary: SummarySink | None = None,
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

    T2 (persistencia de compactación): ``on_message`` devuelve el seq de DB
    asignado (None si no persiste); ``history_seqs`` siembra la lista paralela
    posición→seq al retomar; ``on_summary(from_seq, to_seq, texto)`` avisa
    cuando una compactación reemplaza un rango crudo por un resumen (el
    llamador lo persiste con store.record_summary). ``LoopResult.history``
    trae la history FINAL compactada para que la TUI no re-infle en memoria.

    T1 (cuasi-stall): ``quasi_stall`` activa el detector de bucle
    cuasi-repetitivo (None = desactivado); ``quasi_ask`` es el handler async
    (matches→"seguir"|"redirigir"|"parar") que la TUI usa al superar el
    umbral de ASK. Sin handler (headless) el umbral de ASK degrada a un corte
    honesto stop_reason="stall". El aviso SOFT se inyecta al final del turno
    como user message (NUNCA muta el prefijo cacheable — caching is sacred).
    """
    noop: LoopEvent = lambda kind, data: None  # noqa: E731
    on_event = on_event or noop
    state = LoopState(system=system)
    if history:
        state.history.extend(history)
        state.history_seqs.extend(
            history_seqs
            if history_seqs and len(history_seqs) == len(history)
            else [None] * len(history)
        )
    # Vision v2.1: las imágenes del usuario viajan NATIVAS en el primer
    # mensaje; sus markers de texto se adjuntan al content para que la sesión
    # persistida (que guarda metadata, no píxeles) conserve el registro de
    # qué se mostró.
    prompt_text = user_prompt
    if user_images:
        markers = "\n".join(im.marker() for im in user_images)
        prompt_text = f"{user_prompt}\n{markers}" if user_prompt else markers
    first = Message(role="user", content=prompt_text, images=user_images)
    _append(state, first, on_message)
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
            on_summary=on_summary,
            quasi_stall=quasi_stall,
            quasi_ask=quasi_ask,
        )
    except _Abort as ab:
        return _result(
            state,
            final_text=ab.final_text or "(ejecución abortada por el usuario)",
            stop_reason="aborted",
        )
    except ProviderError as e:
        return _result(state, final_text="", stop_reason="error", error=f"{e.kind}: {e}")
    finally:
        if prev_handler is not None:
            signal.signal(signal.SIGINT, prev_handler)


def _append(state: LoopState, message: Message, on_message: MessageSink | None) -> None:
    """T2: añade a la history Y a la lista paralela posición→seq de DB.

    ``on_message`` devuelve el seq asignado por el store (o None si no se
    persiste). Las dos listas crecen en lockstep: la compactación necesita
    traducir posiciones de history a rangos de seq para record_summary."""
    state.history.append(message)
    seq = on_message(message) if on_message is not None else None
    state.history_seqs.append(seq)


def _result(
    state: LoopState, *, final_text: str, stop_reason: str, error: str | None = None
) -> LoopResult:
    """T2: LoopResult SIEMPRE carga la history final (post-compactación) y sus
    seqs paralelos — la TUI los re-siembra en la siguiente corrida."""
    return LoopResult(
        final_text=final_text,
        stop_reason=stop_reason,
        turns=state.turns,
        usage=state.usage,
        error=error,
        history=list(state.history),
        history_seqs=list(state.history_seqs),
    )


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
    on_message: MessageSink | None = None,
    *,
    stall_repeats: int = 3,
    control: LoopControl | None = None,
    on_summary: SummarySink | None = None,
    quasi_stall: QuasiStallConfig | None = None,
    quasi_ask: QuasiAskHandler | None = None,
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
            _append(state, interj, on_message)
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
                # T2: si un rango crudo fue reemplazado por un resumen, avisar
                # al sink de persistencia con el rango de seqs de DB cubierto
                # (append-only: los crudos siguen en messages; summaries gana
                # la fila from_seq→to_seq + texto del marker). El marker tiene
                # seq None en history_seqs (no vive en messages).
                if (
                    report.summarized > 0
                    and report.summary_text is not None
                    and report.head_end >= 0
                    and on_summary is not None
                ):
                    span = state.history_seqs[report.head_end : report.tail_start]
                    nums = [s for s in span if s is not None]
                    if nums:
                        on_summary(nums[0], nums[-1], report.summary_text)
                if report.summarized > 0 and report.head_end >= 0:
                    state.history_seqs = [
                        *state.history_seqs[: report.head_end],
                        None,
                        *state.history_seqs[report.tail_start :],
                    ]
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
            return _result(
                state,
                final_text=last_text,
                stop_reason="budget_exceeded",
                error=breakdown.human(),
            )

        assistant, end, parse_error = await _stream_one_turn(
            provider, state, tools, on_event, control
        )
        state.turns += 1
        _append(state, assistant, on_message)
        if end is not None:
            state.usage = state.usage + end.usage
        on_event("turn_end", {"turn": state.turns, "usage": end.usage if end else Usage()})

        if assistant.content:
            last_text = assistant.content

        if end is None or end.stop_reason == "error":
            err = (end.error if end else "stream ended without MessageEnd") or parse_error
            return _result(state, final_text=last_text, stop_reason="error", error=err)
        if end.stop_reason == "refusal":
            return _result(state, final_text=last_text, stop_reason="refusal")
        if end.stop_reason == "max_tokens" and not assistant.tool_calls:
            return _result(state, final_text=last_text, stop_reason="max_tokens")

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
                _append(state, steer_msg, on_message)
                on_event("steering", {"text": steer})
                continue
            return _result(state, final_text=last_text, stop_reason="end_turn")

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
            _append(state, tool_msg, on_message)

        # T1 — Cuasi-stall: firma NORMALIZADA del turno contra la ventana
        # deslizante. El aviso SOFT entra como user message al FINAL del turno
        # (frontera de mensaje, nunca mid-stream; el prefijo cacheable intacto).
        if quasi_stall is not None and quasi_stall.enabled and assistant.tool_calls:
            qsig = _quasi_signature(assistant.tool_calls)
            assert qsig is not None  # tool_calls no vacío ⇒ firma no None
            matches = _quasi_count(qsig, state.quasi_window, quasi_stall.similarity)
            state.quasi_window.append(qsig)
            if len(state.quasi_window) > quasi_stall.window:
                state.quasi_window.popleft()
            if matches >= quasi_stall.ask_count:
                on_event(
                    "quasi_stall_ask",
                    {"matches": matches, "window": quasi_stall.window},
                )
                decision: QuasiAskDecision = "parar"
                if quasi_ask is not None:
                    raw = await quasi_ask(matches)
                    if raw in QUASI_ASK_OPTIONS:
                        decision = raw
                if decision == "parar":
                    msg = (
                        f"bucle cuasi-repetitivo: {matches} llamadas cuasi-idénticas "
                        f"(similitud ≥{quasi_stall.similarity:.0%}) en las últimas "
                        f"{quasi_stall.window}"
                        + (
                            "; el usuario decidió parar."
                            if quasi_ask is not None
                            else "; sin canal de pregunta en modo headless — corrida "
                            "detenida honestamente."
                        )
                    )
                    on_event("quasi_stall_stop", {"matches": matches})
                    return _result(state, final_text=last_text, stop_reason="stall", error=msg)
                if decision == "redirigir":
                    state.quasi_window.clear()
                    note = (
                        "[REDIRECCIÓN DEL USUARIO] El usuario detectó un bucle "
                        "cuasi-repetitivo y pidió redirigir. Pregunta qué enfoque "
                        "quiere y NO vuelvas a la estrategia anterior."
                    )
                else:  # seguir
                    state.quasi_window.clear()
                    note = (
                        "[DECISIÓN DEL USUARIO] Pese al bucle cuasi-repetitivo el "
                        "usuario decidió SEGUIR. Continúa, pero cambia de estrategia "
                        "si el resultado no llega."
                    )
                note_msg = Message(role="user", content=note)
                _append(state, note_msg, on_message)
            elif matches >= quasi_stall.warn_count and matches > state.quasi_last_warned:
                state.quasi_last_warned = matches
                on_event(
                    "quasi_stall_warning",
                    {
                        "matches": matches,
                        "window": quasi_stall.window,
                        "similarity": quasi_stall.similarity,
                    },
                )
                warn = QUASI_WARN_TEMPLATE.format(
                    n=matches,
                    pct=int(quasi_stall.similarity * 100),
                    w=quasi_stall.window,
                )
                warn_msg = Message(role="user", content=warn)
                _append(state, warn_msg, on_message)
        elif assistant.tool_calls:
            # Sin detector activo la ventana no se llena (costo cero).
            pass

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
                return _result(state, final_text=last_text, stop_reason="stall", error=msg)
        elif stall_repeats > 0:
            prev_signature = None
            repeat_count = 0

        await asyncio.sleep(0)  # yield to event loop (signal delivery)

    return _result(state, final_text=last_text, stop_reason="max_turns")
