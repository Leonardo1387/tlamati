"""A6 — Context compaction: M2 microcompaction + cheap-model summary.

Token-saving map (research/04, 5 layers, cheapest first): truncate at the
spout (M1, tools/builtin) → MICROCOMPACT (M2, this module) → budget check
(context/budget.py) → SUMMARY with a cheap model (this module) → fresh window
(last resort, honest marker).

GOLDEN RULE ("caching is sacred", PRD invariant #1): compaction rebuilds the
history SUFFIX only. The cacheable prefix — system prompt, tools, and the
anchored head of the conversation — is NEVER mutated. On Anthropic the cache
breakpoints live on the last system block + last tool, so every edit here
happens behind them; on prefix-caching gateways (OpenRouter) the head anchor
keeps the earliest messages byte-stable.

M2 microcompaction (donor: qwen-code microcompact.ts, Apache-2.0):
- Only RE-FETCHABLE tool outputs are cleared (COMPACTABLE_TOOLS whitelist).
  PITFALL from the donor (their issue #4239): any new file-touching tool MUST
  be added to the whitelist or its output gets blanked without eviction
  report — so the eviction sets ToolResult.microcompacted=True permanently.
- Placeholder + anti-collision: a result is "already cleared" ONLY on exact
  match of the placeholder constant; user text that merely starts with the
  prefix is never misclassified.
- Errors are never cleared (small, and they carry lessons).
- Recent tool outputs are retained (donor: codex compact_retained_tool_outputs
  — retain_across_windows): the last ``retain_recent`` messages are untouchable.

Summary compaction: middle of the history (between head anchor and recent
window) is rendered to text and summarized by a CHEAP model with a fallback
chain. If every model in the chain fails, we degrade to a budget-compaction
window drop (donor: codex compact_token_budget.rs — sometimes a fresh window
is cheaper than summarizing) with an HONEST marker, never a silent loss.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from tlamati.context.budget import Budget
from tlamati.core.messages import Message, MessageEnd, TextDelta, Usage
from tlamati.providers.base import Provider, ProviderError, ToolSpec

# Donor constant (qwen MICROCOMPACT_CLEARED_MESSAGE). Model-facing; English on
# purpose so it reads as system vocabulary, not user text.
CLEARED_PLACEHOLDER = "[Old tool result content cleared]"

# Tools whose output can be re-obtained by calling the tool again. tools/builtin
# today; Fase B registry must keep this list in sync (donor pitfall #4239).
DEFAULT_COMPACTABLE_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "write_file",
        "terminal",
        "grep",
        "glob",
        "web_fetch",
        "search_memory",
        "skill_view",  # C3: re-fetchable from disk (GUIA C3 destilada)
        "skill_list",
    }
)

SUMMARY_SYSTEM = (
    "Eres un compresor de contexto de un agente de terminal. Resume la "
    "conversación parcial que recibas preservando TODO lo accionable: estado "
    "de la tarea, archivos tocados (rutas exactas), cambios hechos, errores "
    "encontrados y su resolución, y el siguiente paso pendiente. Sé denso y "
    "factual; sin saludos ni relleno. Máximo ~300 palabras."
)


@dataclass(frozen=True)
class CompactionConfig:
    """Knobs for both M2 and summary compaction."""

    retain_first: int = 2  # head anchor: first user prompt + first assistant reply
    retain_recent: int = 8  # untouchable tail (codex retain_across_windows)
    min_summary_target: int = 4  # don't summarize fewer middle messages than this
    min_chars_to_clear: int = 200  # clearing tiny outputs isn't worth the churn
    compactable_tools: frozenset[str] = DEFAULT_COMPACTABLE_TOOLS


@dataclass(frozen=True)
class CompactionReport:
    """What one compaction pass did — feeds the audit trail and evals.

    T2 (persistencia de compactación): cuando ``summarized > 0``, el rango
    ``[head_end, tail_start)`` de la history DE ENTRADA fue reemplazado por un
    único mensaje cuyo contenido completo viaja en ``summary_text`` (ya con su
    marker). El llamador que persista (loop → store.record_summary) usa el
    rango para mapear posiciones a seqs de DB; el texto permite reconstruir la
    MISMA history al retomar (append-only: los mensajes crudos nunca se borran
    de la tabla messages).
    """

    microcompacted: int = 0  # tool results cleared to placeholder
    summarized: int = 0  # middle messages replaced by the summary
    summary_failed: bool = False  # fell back to honest window drop
    tokens_before: int = 0
    tokens_after: int = 0
    usage: Usage = field(default_factory=Usage)  # summarizer spend, folded into loop
    head_end: int = -1  # inicio del rango reemplazado (exclusive head anchor)
    tail_start: int = -1  # fin del rango reemplazado (inicio de la cola reciente)
    summary_text: str | None = None  # contenido COMPLETO del mensaje insertado


@runtime_checkable
class Summarizer(Protocol):
    """Returns (summary_text | None, usage). None = whole chain failed."""

    async def summarize(self, transcript: str) -> tuple[str | None, Usage]: ...


class ModelSummarizer:
    """Summarizer backed by a CHEAP model with fallback chain (GUIA A6).

    Each provider is tried in order; a ProviderError, an error MessageEnd, or
    an empty summary advances to the next model. Usage from the successful
    call is returned so the loop can account for it.
    """

    def __init__(self, providers: Sequence[Provider], max_transcript_chars: int = 60_000) -> None:
        self.providers = providers
        self.max_transcript_chars = max_transcript_chars

    async def summarize(self, transcript: str) -> tuple[str | None, Usage]:
        text = transcript[: self.max_transcript_chars]
        last_usage = Usage()
        for provider in self.providers:
            try:
                out_parts: list[str] = []
                usage = Usage()
                failed = False
                messages = [Message(role="user", content=text)]
                async for ev in provider.stream(messages, ()):
                    if isinstance(ev, TextDelta):
                        out_parts.append(ev.text)
                    elif isinstance(ev, MessageEnd):
                        usage = usage + ev.usage
                        if ev.stop_reason == "error":
                            failed = True
                summary = "".join(out_parts).strip()
                if summary and not failed:
                    return summary, usage
                last_usage = last_usage + usage
            except ProviderError:
                continue  # fallback chain: try next cheap model
        return None, last_usage


def _tool_name_by_call_id(history: Sequence[Message]) -> dict[str, str]:
    names: dict[str, str] = {}
    for m in history:
        for tc in m.tool_calls:
            names[tc.id] = tc.name
    return names


def _is_cleared(content: str) -> bool:
    """Anti-collision predicate: EXACT match only (donor regex lesson — text
    that merely starts with the placeholder is user content, never a marker)."""
    return content.strip() == CLEARED_PLACEHOLDER


def microcompact(history: Sequence[Message], config: CompactionConfig) -> tuple[list[Message], int]:
    """M2: clear old re-fetchable tool outputs. Returns (new history, cleared).

    Only touches messages OUTSIDE the head anchor and the recent tail. Never
    clears errors, never clears untrusted-flagged results twice, never clears
    outputs that are already placeholders (idempotent — safe to call every turn).
    """
    n = len(history)
    cutoff = max(config.retain_first, n - config.retain_recent)
    names = _tool_name_by_call_id(history)
    out: list[Message] = []
    cleared = 0
    for i, m in enumerate(history):
        tr = m.tool_result
        if (
            i < cutoff
            and m.role == "tool"
            and tr is not None
            and not tr.is_error
            and not tr.microcompacted
            and not _is_cleared(tr.content)
            # Vision v2.1: un resultado con imágenes se limpia aunque su texto
            # sea corto (el marker) — los píxeles son el costo, y read_file los
            # re-obtiene. Limpiar SOLO el texto dejaría el bloque de visión
            # vivo: una evicción a medias, peor que no evictar.
            and (len(tr.content) >= config.min_chars_to_clear or bool(tr.images))
            and names.get(tr.tool_call_id, "") in config.compactable_tools
        ):
            m = replace(
                m,
                tool_result=replace(
                    tr, content=CLEARED_PLACEHOLDER, microcompacted=True, images=()
                ),
            )
            cleared += 1
        out.append(m)
    return out, cleared


def render_for_summary(messages: Sequence[Message], max_chars_per_result: int = 500) -> str:
    """Flatten the middle of the history into text for the cheap model."""
    lines: list[str] = []
    for m in messages:
        if m.role == "tool" and m.tool_result is not None:
            body = m.tool_result.content[:max_chars_per_result]
            lines.append(f"[tool_result {m.tool_result.tool_call_id}] {body}")
        elif m.tool_calls:
            calls = "; ".join(f"{tc.name}({tc.raw_arguments[:200]})" for tc in m.tool_calls)
            lines.append(f"[assistant] {m.content}\n[calls] {calls}")
        else:
            # Vision v2.1: el summarizer es ciego a píxeles; los markers de
            # texto viajan para que el resumen diga QUÉ imágenes hubo.
            imgs = "".join(f" {im.marker()}" for im in m.images)
            lines.append(f"[{m.role}] {m.content}{imgs}")
    return "\n".join(lines)


def _summary_message(summary: str) -> Message:
    """The summary enters as ONE user message with a loud marker. This is the
    sanctioned exception to 'no synthetic user messages' (it IS the explicit
    compaction, hermes AGENTS.md), and it lands at a message boundary — never
    mid-stream; the loop calls compaction only between turns."""
    return Message(
        role="user",
        content=("[CONTEXTO COMPACTADO — resumen de los mensajes anteriores] " + summary),
    )


def _window_drop_message(dropped: int) -> Message:
    return Message(
        role="user",
        content=(
            f"[COMPACTACIÓN DE EMERGENCIA] El resumen con modelo falló y el "
            f"presupuesto estaba excedido: se descartaron {dropped} mensajes "
            "antiguos (presupuesto-compaction, patrón codex). El contenido "
            "anterior NO está disponible; re-lee archivos si necesitas detalles."
        ),
    )


class Compactor:
    """One compaction pass over the history SUFFIX (golden rule above).

    Trigger policy (maps to the 5-layer ladder):
    - budget status "warn"     → M2 microcompaction only (free, no model call).
    - budget status "exceeded" → M2 + summary (or honest window drop if the
      whole cheap-model chain fails — a fresh window beats a dead loop).
    """

    def __init__(
        self,
        config: CompactionConfig | None = None,
        summarizer: Summarizer | None = None,
    ) -> None:
        self.config = config or CompactionConfig()
        self.summarizer = summarizer

    async def compact(
        self,
        history: Sequence[Message],
        *,
        system: str,
        tools: Sequence[ToolSpec],
        budget: Budget,
        status: str,
    ) -> tuple[list[Message], CompactionReport | None]:
        cfg = self.config
        tokens_before = budget.breakdown(system, tools, history).total

        # Layer M2: free eviction of old re-fetchable tool outputs.
        new_history, cleared = microcompact(history, cfg)

        report = CompactionReport(microcompacted=cleared, tokens_before=tokens_before)
        summarized = 0

        if status == "exceeded" and self.summarizer is not None:
            n = len(new_history)
            head_end = min(cfg.retain_first, n)
            tail_start = max(head_end, n - cfg.retain_recent)
            middle = new_history[head_end:tail_start]
            if len(middle) >= cfg.min_summary_target:
                transcript = render_for_summary(middle)
                summary, usage = await self.summarizer.summarize(transcript)
                report = replace(report, usage=report.usage + usage)
                if summary is not None:
                    marker_msg = _summary_message(summary)
                else:
                    # Honest degradation: window drop with a loud marker.
                    marker_msg = _window_drop_message(len(middle))
                    report = replace(report, summary_failed=True)
                new_history = [
                    *new_history[:head_end],
                    marker_msg,
                    *new_history[tail_start:],
                ]
                summarized = len(middle)
                # T2: microcompact preserva posiciones (mismo len que history),
                # así que head_end/tail_start son índices válidos de la history
                # DE ENTRADA — el loop los usa para mapear a seqs de DB.
                report = replace(
                    report,
                    head_end=head_end,
                    tail_start=tail_start,
                    summary_text=marker_msg.content,
                )

        if cleared == 0 and summarized == 0:
            return list(history), None  # nothing to do — no report, no churn

        report = replace(
            report,
            summarized=summarized,
            tokens_after=budget.breakdown(system, tools, new_history).total,
        )
        return new_history, report
