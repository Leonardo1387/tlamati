"""D1 — subagent/spawn.py: delegación con límites (F9, PRD SHOULD).

Patrón donor: hermes delegate_task (MIT, semántica sancionada) + Raschka #6
(límites duros: max_turns + tope de gasto). Reglas del HANDOFF_FASE_D §3:

- Tool `delegate_task`: args goal/context/max_turns. Permission ASK por
  default (un subagente suelto es costo suelto).
- El hijo corre run_loop RECURSIVO con Registry reducido READ-ONLY (semilla:
  PLAN_READONLY_TOOLS), Budget propio cuyo tope hereda del padre, mismo
  provider. Sin sandbox-net nuevo (las tools del hijo no lo necesitan).
- PROFUNDIDAD MÁXIMA = 1: el hijo NUNCA registra delegate_task — fail fast
  al construir su Registry (ValueError → resultado honesto, no excepción muda).
- DECISIÓN ZANJADA (fundador, 17-nov): el hijo NUNCA tiene más poder que el
  padre — toolset read-only, sin escritura; la escalera solo ENDURECE.
- El padre recibe SOLO el resumen final (LoopResult.final_text + metadata
  honesta de parada) — NUNCA el transcript del hijo (invariante de contexto).
- AUDITORÍA: los eventos del hijo van al MISMO ledger con prefijo de sesión
  hija (``<parent>:sub-NN``) — decisión (a) del handoff: NO se migra el
  schema B5. Nada de ejecuciones invisibles.
- El tool NO entra a DEFAULT_COMPACTABLE_TOOLS (tiene side-effect: gasta).
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from tlamati.context.budget import Budget
from tlamati.core.loop import LoopResult, run_loop
from tlamati.core.messages import Event, Message, MessageEnd
from tlamati.plan.mode import PLAN_READONLY_TOOLS
from tlamati.plugins import HookRegistry
from tlamati.policy.ledger import Ledger
from tlamati.providers.base import Provider, ProviderError, ToolSpec
from tlamati.tools.registry import Permission, Registry, Tool

DELEGATE_TOOL_NAME = "delegate_task"

SUBAGENT_SYSTEM = (
    "Eres un SUBAGENTE de Tlamati: un hijo de SOLO LECTURA creado para una "
    "tarea concreta. Explora con las tools disponibles (todas read-only) y "
    "cierra con un RESUMEN útil para tu padre: qué encontraste, qué falta y "
    "qué recomiendas. No puedes escribir archivos, ni ejecutar comandos, ni "
    "crear otros subagentes. Tu padre solo recibirá tu último mensaje — sé "
    "breve, concreto y honesto."
)

DELEGATE_PROMPT_BLOCK = f"""
# DELEGACIÓN (subagentes)
Dispones del tool `{DELEGATE_TOOL_NAME}`(goal, context, max_turns): crea UN
subagente de solo lectura que explora por ti y te devuelve ÚNICAMENTE su
resumen final (nunca su transcript completo). Úsalo para investigación que
inundaría tu contexto. El subagente NUNCA tiene más poder que tú: no escribe,
no ejecuta, no delega (profundidad máxima 1). Cuesta dinero: requiere
aprobación y tiene topes duros de turnos y tokens.
"""


@dataclass(frozen=True)
class SubagentConfig:
    """Límites duros del hijo (donor Raschka #6). El padre los crea; el hijo
    los hereda y NUNCA puede relajarlos."""

    max_turns_default: int = 10
    max_turns_cap: int = 25  # techo absoluto aunque el modelo pida más
    max_total_tokens: int = 200_000  # tope de gasto acumulado (in+out)
    max_context_tokens: int = 128_000  # tope de ventana — se hereda del padre

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, parent_context: int) -> SubagentConfig:
        raw = data or {}

        def _int(key: str, default: int) -> int:
            v = raw.get(key)
            return int(v) if isinstance(v, int) and v > 0 else default

        return cls(
            max_turns_default=_int("max_turns_default", cls.max_turns_default),
            max_turns_cap=_int("max_turns_cap", cls.max_turns_cap),
            max_total_tokens=_int("max_total_tokens", cls.max_total_tokens),
            # El tope de contexto del hijo NUNCA supera al del padre (hereda).
            max_context_tokens=min(_int("max_context_tokens", parent_context), parent_context),
        )


class _CappedProvider:
    """Envoltorio del provider del padre que impone el tope de gasto del hijo.

    Cuenta tokens acumulados (in+out) tras cada MessageEnd; si el siguiente
    turno rompería el tope, falla con ProviderError ANTES de gastar (mismo
    patrón de inversión que el Budget en A5: nunca gastar y luego lamentar)."""

    def __init__(self, inner: Provider, max_total_tokens: int) -> None:
        self._inner = inner
        self._max = max_total_tokens
        self.total_tokens = 0
        self.capped = False

    @property
    def model(self) -> str:
        return self._inner.model

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        if self.total_tokens >= self._max:
            self.capped = True
            raise ProviderError(
                f"subagente: tope de gasto alcanzado ({self.total_tokens} tokens >= {self._max})",
                kind="config",
            )
        async for ev in self._inner.stream(messages, tools):
            if isinstance(ev, MessageEnd) and ev.usage is not None:
                self.total_tokens += ev.usage.input_tokens + ev.usage.output_tokens
            yield ev


def build_child_tools(
    candidates: Sequence[Tool],
) -> list[Tool]:
    """Registry del hijo: SOLO tools read-only de la whitelist, SOLO permiso
    AUTO (la escalera solo endurece hacia abajo — decisión zanjada). Fail fast:
    un delegate_task aquí sería un nieto (profundidad 2) = error honesto, no
    excepción muda ni filtrado silencioso de poder extra."""
    for t in candidates:
        if t.name == DELEGATE_TOOL_NAME:
            raise ValueError("un subagente no puede registrar delegate_task (profundidad máxima 1)")
    child: list[Tool] = []
    for t in candidates:
        if t.name not in PLAN_READONLY_TOOLS:
            continue  # todo lo que no es read-only simply no existe para el hijo
        if t.permission is not Permission.AUTO:
            continue  # endurecer: nada que requiera aprobación del usuario
        child.append(t)
    return child


def _render_result(result: LoopResult, capped: _CappedProvider, child_session: str | None) -> str:
    """Lo que el padre ve: metadata honesta + SOLO el resumen final."""
    u = result.usage
    lines = [
        f"[subagente] stop={result.stop_reason} turnos={result.turns} "
        f"tokens: in={u.input_tokens} out={u.output_tokens}"
        + (f" sesión={child_session}" if child_session else "")
    ]
    if capped.capped:
        lines.append(
            "[subagente] detenido por TOPE DE GASTO (max_total_tokens)"
            " — el resumen puede estar incompleto"
        )
    if result.stop_reason == "max_turns":
        lines.append(
            "[subagente] detenido por LÍMITE DE TURNOS — el resumen puede estar incompleto"
        )
    if result.error:
        lines.append(f"[subagente] error: {result.error}")
    lines.append(result.final_text.strip() or "(el subagente no produjo resumen)")
    return "\n".join(lines)


def make_delegate_tool(
    provider: Provider,
    *,
    tool_candidates: Callable[[], list[Tool]],
    config: SubagentConfig,
    ledger: Ledger | None = None,
    hooks: HookRegistry | None = None,
) -> Tool:
    """Tool `delegate_task` del PADRE. ``tool_candidates`` es una fábrica que
    devuelve las tools disponibles en la corrida; el filtrado read-only ocurre
    en cada spawn (build_child_tools). D2: ``hooks`` (HookRegistry) se hereda
    al Registry del hijo — la escalera solo ENDURECE: si un plugin del padre
    veta un tool, el veto también aplica dentro del subagente."""
    spawn_seq = itertools.count(1)

    async def _run(args: dict[str, Any]) -> str:
        goal = str(args.get("goal") or "").strip()
        if not goal:
            return "ERROR: delegate_task requiere un 'goal' no vacío"
        context = str(args.get("context") or "").strip()
        raw_turns = args.get("max_turns") or config.max_turns_default
        try:
            max_turns = min(int(raw_turns), config.max_turns_cap)
        except (TypeError, ValueError):
            max_turns = config.max_turns_default

        # Fail fast: profundidad 1 (nietos = error honesto).
        try:
            child_tools = build_child_tools(tool_candidates())
        except ValueError as e:
            return f"ERROR: {e}"
        if not child_tools:
            return (
                "ERROR: no hay tools read-only disponibles para el subagente "
                "(el hijo solo puede explorar; nada que delegar)"
            )

        # Auditoría: MISMO ledger, prefijo de sesión hija (no se migra schema).
        child_ledger: Ledger | None = None
        child_session: str | None = None
        if ledger is not None and not ledger.broken:
            child_session = f"{ledger.session_id}:sub-{next(spawn_seq):02d}"
            try:
                child_ledger = Ledger(ledger.db_path, child_session)
            except Exception:
                # auditoría rota no impide delegar (degradación honesta B5)
                child_ledger = None
                child_session = None

        capped = _CappedProvider(provider, config.max_total_tokens)

        def _child_event(kind: str, data: dict[str, Any]) -> None:
            if child_ledger is not None and kind == "turn_end":
                child_ledger.turn = data["turn"]
                u = data["usage"]
                child_ledger.record_turn_cost(
                    turn=data["turn"],
                    input_tokens=u.input_tokens,
                    output_tokens=u.output_tokens,
                    cache_read=u.cache_read_tokens,
                    cost_usd=u.cost_usd,
                )

        prompt = f"# TAREA\n{goal}" + (f"\n\n# CONTEXTO DEL PADRE\n{context}" if context else "")
        try:
            result = await run_loop(
                capped,
                system=SUBAGENT_SYSTEM,
                user_prompt=prompt,
                tools=Registry(child_tools, ledger=child_ledger, hooks=hooks),
                budget=Budget(max_context_tokens=config.max_context_tokens),
                max_turns=max_turns,
                on_event=_child_event,
            )
        finally:
            if child_ledger is not None:
                child_ledger.close()
        return _render_result(result, capped, child_session)

    return Tool(
        name=DELEGATE_TOOL_NAME,
        description=(
            "Crea UN subagente de solo lectura (read_file/search_files/skills/memoria) "
            "que trabaja una tarea aislada y devuelve SOLO su resumen final. El hijo no "
            "puede escribir, ejecutar, ni delegar (profundidad 1). Topes duros: "
            f"max_turns<={config.max_turns_cap}, gasto<={config.max_total_tokens} tokens."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Qué debe averiguar/hacer el subagente (autocontenido)",
                },
                "context": {
                    "type": "string",
                    "description": "Contexto que el hijo necesita (rutas, restricciones)",
                },
                "max_turns": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": config.max_turns_cap,
                    "description": f"Tope de turnos del hijo (default: {config.max_turns_default})",
                },
            },
            "required": ["goal"],
        },
        run=_run,
        # ASK por default: un subagente suelto es costo suelto (handoff §3 D1).
        permission=Permission.ASK,
        # NO sandboxable (no ejecuta nada propio), NO untrusted (es nuestro).
    )
