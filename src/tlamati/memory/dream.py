"""C2 — AUTO-DREAM: background memory consolidation at session close.

Donor: Claude Code (research/05 §3): memory distillation NEVER runs in the hot
turn — it is an asynchronous job at session close (CC "auto-dream"). qwen-code
agrees: memory extraction is a separate planner, not part of the main loop.

v1 (GUIA C2 destilada): ONE cheap-model call with the session transcript; the
model returns JSON memory operations which are applied through the SAME
capped, atomic MemoryStore batch (so the dream can never overflow the caps —
a dreaming agent that fills memory is the failure mode the caps exist for).

Cost discipline: dream is opt-in per run (--dream flag / config), uses the
compact-model chain (cheap), and degrades honestly to a no-op on any failure.
The transcript comes from the session store (C1) — already on disk, free.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from tlamati.context.compaction import Summarizer
from tlamati.core.messages import Message
from tlamati.memory.store import MemoryError, MemoryStore

DREAM_SYSTEM = (
    "Eres el consolidador de memoria de un agente de terminal. Recibes la "
    "transcripción de una sesión terminada. Extrae SOLO hechos durables que "
    "importarán en sesiones futuras: decisiones del usuario, preferencias "
    "expresadas, correcciones que hizo, convenciones del proyecto, errores "
    "resueltos y su causa raíz. NO extraigas: progreso de tareas, resúmenes "
    "de la conversación, datos que cambian pronto. Responde EXCLUSIVAMENTE un "
    'JSON: {"operations": [{"target": "memory"|"user", "action": '
    '"add"|"replace"|"remove", "content": "...", "old_text": '
    '"..."}], "gaps": [...]}. "gaps": 0-3 frases cortas señalando qué NO '
    "quedó en memoria y probablemente importará después (temas que el usuario "
    "mencionó de pasada, decisiones sin registrar, posibles contradicciones "
    "con entradas existentes). Si no hay huecos: lista vacía. Si no hay nada "
    'durable: {"operations": [], "gaps": []}. Máximo 5 '
    "operaciones. Entradas cortas (1-2 líneas), declarativas, en el idioma "
    "del usuario."
)

MAX_TRANSCRIPT_CHARS = 40_000


@dataclass(frozen=True)
class DreamReport:
    applied: int = 0
    skipped_reason: str | None = None
    gaps: tuple[str, ...] = ()

    def human(self) -> str:
        base = (
            f"[dream] sin consolidar: {self.skipped_reason}"
            if self.skipped_reason
            else f"[dream] {self.applied} entrada(s) consolidada(s) en memoria"
        )
        if self.gaps:
            base += f"; {len(self.gaps)} hueco(s): " + " | ".join(self.gaps)
        return base


def transcript_from_messages(messages: list[Message]) -> str:
    """Render the session for the dream call (roles + text only; tool bodies
    are noise for memory extraction — keep names, drop content)."""
    lines: list[str] = []
    for m in messages:
        if m.role == "assistant":
            if m.content:
                lines.append(f"asistente: {m.content}")
            for tc in m.tool_calls:
                lines.append(f"asistente usó tool: {tc.name}")
        elif m.role == "user":
            lines.append(f"usuario: {m.content}")
        elif m.role == "tool" and m.tool_result is not None:
            tr = m.tool_result
            snippet = tr.content[:200] + ("..." if len(tr.content) > 200 else "")
            lines.append(f"tool_result{' (error)' if tr.is_error else ''}: {snippet}")
    return "\n".join(lines)[:MAX_TRANSCRIPT_CHARS]


def parse_dream_output(raw: str) -> tuple[list[dict[str, str]], list[str]]:
    """Extract the operations array (G2: + gaps) from the model reply,
    tolerating code fences and leading prose (models love wrapping JSON).

    G2 gap-analysis (donor: gbrain think): "gaps" = advisory phrases about
    what did NOT make it into memory. Caps: max 3 gaps, 300 chars each.
    """
    text = raw.strip()
    if text.startswith("```"):
        # strip fence lines
        parts = text.split("\n")
        text = "\n".join(p for p in parts if not p.strip().startswith("```")).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("respuesta sin JSON")
    data = json.loads(text[start : end + 1])
    ops = data.get("operations")
    if not isinstance(ops, list):
        raise ValueError("JSON sin 'operations' lista")
    clean: list[dict[str, str]] = []
    for op in ops[:5]:
        if isinstance(op, dict) and op.get("action") in ("add", "replace", "remove"):
            clean.append({str(k): str(v) for k, v in op.items()})
    raw_gaps = data.get("gaps")
    gaps: list[str] = []
    if isinstance(raw_gaps, list):
        for g in raw_gaps:
            if len(gaps) >= 3:
                break
            if isinstance(g, str) and g.strip():
                gaps.append(g.strip()[:300])
    return clean, gaps


async def dream(store: MemoryStore, summarizer: Summarizer, messages: list[Message]) -> DreamReport:
    """Run consolidation. NEVER raises: any failure = honest skip report."""
    if not messages:
        return DreamReport(skipped_reason="sesión vacía")
    transcript = transcript_from_messages(messages)
    if len(transcript.strip()) < 200:
        return DreamReport(skipped_reason="transcripción demasiado corta")
    prompt = (
        f"{DREAM_SYSTEM}\n\nTranscripción de la sesión:\n\n{transcript}\n\n"
        "Devuelve el JSON de operaciones de memoria (o lista vacía)."
    )
    try:
        text, _usage = await summarizer.summarize(prompt)
    except Exception as e:
        return DreamReport(skipped_reason=f"modelo falló: {e}")
    if not text:
        return DreamReport(skipped_reason="modelo devolvió vacío")
    try:
        ops, gaps = parse_dream_output(text)
    except (ValueError, json.JSONDecodeError) as e:
        return DreamReport(skipped_reason=f"respuesta no es JSON válido: {e}")
    if not ops:
        return DreamReport(skipped_reason="nada durable que guardar", gaps=tuple(gaps))
    applied = 0
    for op in ops:
        target = op.pop("target", "memory")
        if target not in ("memory", "user"):
            target = "memory"
        try:
            store.apply_batch(target, [op])
            applied += 1
        except MemoryError:
            # One bad operation must not kill the rest (per-op atomicity here;
            # the batch atomicity is for the agent-facing tool).
            continue
    if applied == 0:
        return DreamReport(
            skipped_reason="todas las operaciones fueron rechazadas (caps)",
            gaps=tuple(gaps),
        )
    # G2: gaps = advisory puro, NUNCA se escriben a archivo (invariante 3).
    return DreamReport(applied=applied, gaps=tuple(gaps))
