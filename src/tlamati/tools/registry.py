"""B1 — Tool registry: the formal tool contract.

Replaces the provisional ``tools_min`` (Fase A). A Tool declares:

- ``name`` / ``description`` / ``input_schema`` — what the model sees.
- ``permission`` — auto | ask | deny (policy enforcement arrives in B4; here
  the registry already HONOURS the flag: ``deny`` never runs, ``ask`` without
  an approver degrades to an honest error, ``auto`` runs).
- ``sandboxable`` — whether B3 (bwrap) may jail its execution.
- ``run`` — async callable(dict) -> str. Errors are RETURNED as "ERROR: ..."
  strings; unexpected exceptions are caught and converted (the loop never
  crashes on a tool bug — Fase A invariant).

Validation ladder (jsonschema BEFORE execution):
1. args parse (the loop already does JSON parsing; registry re-checks type),
2. schema validation → honest ERROR ToolResult so the model self-corrects,
3. permission gate,
4. run + truncation at the spout (M1).

Footprint rule (hermes AGENTS.md ladder): prefer extending an existing tool
over adding a new core tool.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import jsonschema
from jsonschema.exceptions import SchemaError

from tlamati.core.messages import ToolResult
from tlamati.plugins import HookRegistry
from tlamati.plugins.internal.ledger_plugin import register_ledger_hooks
from tlamati.providers.base import ToolSpec

if TYPE_CHECKING:  # B4: policy.config importa Permission de aquí → ciclo evitado
    from tlamati.context.late_instructions import LateInstructions
    from tlamati.policy.config import Policy
    from tlamati.policy.ledger import Ledger

MAX_OUTPUT_CHARS = 50_000  # M1: truncate at the spout, honest marker


class Permission(StrEnum):
    """Policy ladder (GUIA §B4). B1 only honours the flag; B4 wires config."""

    AUTO = "auto"  # runs without asking
    ASK = "ask"  # needs explicit approval (TUI prompt / --approve flag)
    DENY = "deny"  # never runs


# B4 will supply the real approver (TUI/headless policy). Signature:
# (tool_name, args) -> bool. Kept async so a TUI prompt doesn't block the loop.
Approver = Callable[[str, dict[str, Any]], Awaitable[bool]]


@dataclass(frozen=True)
class Tool:
    """The formal tool contract (GUIA §B1)."""

    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[[dict[str, Any]], Awaitable[str]]
    permission: Permission = Permission.AUTO
    sandboxable: bool = False
    produces_untrusted: bool = False  # B4: sus resultados OK marcan la trifecta

    def as_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, input_schema=self.input_schema
        )


def truncate(text: str) -> tuple[str, bool]:
    """M1 spout truncation with an honest marker (shared with B2 tools)."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n... [truncated]", True


def validate_schema(schema: dict[str, Any], args: dict[str, Any]) -> str | None:
    """Return None if args satisfy schema, else an honest error string.

    A malformed SCHEMA is a harness bug (not the model's) — surfaced loudly so
    tests catch it, but still returned as a string, never raised into the loop.
    """
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
    except SchemaError as e:
        return f"ERROR: tool schema is invalid (harness bug): {e.message}"
    errors = sorted(validator.iter_errors(args), key=lambda e: list(e.path))
    if not errors:
        return None
    details = "; ".join(
        f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors[:3]
    )
    return f"ERROR: invalid arguments — {details}"


class Registry:
    """Name → Tool lookup + guarded execution.

    Duplicate names are a programming error (fail fast at register, not at
    dispatch): two tools claiming one name would corrupt every audit trail.
    """

    def __init__(
        self,
        tools: list[Tool] | None = None,
        approver: Approver | None = None,
        policy: Policy | None = None,
        ledger: Ledger | None = None,
        hooks: HookRegistry | None = None,
        late_instructions: LateInstructions | None = None,
    ):
        self._tools: dict[str, Tool] = {}
        self.approver = approver
        self.policy = policy  # B4: overrides + patrones + trifecta
        self.ledger = ledger  # B5: auditoría append-only (None = off)
        # NIVEL 1a (dogfood #6): inyección tardía de AGENTS.md cuando el
        # agente toca un repo FUERA del cwd inicial. Advisory: adjunta un
        # recordatorio al tool result (mensaje nuevo), nunca muta el prefijo.
        self.late_instructions = late_instructions
        # D2: hooks (plugins). Con ledger, el plugin INTERNO de auditoría se
        # registra SIEMPRE (B5 no es opcional; migración real de _log): el
        # registro de tool_events ahora vive en after_tool de ese plugin.
        self.hooks = hooks if hooks is not None else HookRegistry()
        if ledger is not None:
            register_ledger_hooks(self.hooks, ledger)
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool registration: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def specs(self) -> list[ToolSpec]:
        """Wire specs for the provider call (stable order = stable prefix)."""
        return [t.as_spec() for t in self._tools.values()]

    async def execute(self, name: str, args: dict[str, Any], tool_call_id: str) -> ToolResult:
        """Guarded execution: unknown → schema → plugin veto → permission → run.

        EVERY failure mode becomes an honest ToolResult(is_error=True); this
        method never raises (loop invariant from Fase A). B5/D2: cada salida
        dispara ``after_tool`` (el plugin interno de auditoría la registra con
        su decisión — migración real del viejo _log hardcoded)."""

        def _log(
            decision: str,
            result: ToolResult,
            logged_args: dict[str, Any] | None = None,
        ) -> ToolResult:
            self.hooks.fire_after_tool(
                name, logged_args if logged_args is not None else (args or {}), decision, result
            )
            return result

        tool = self._tools.get(name)
        if tool is None:
            return _log(
                "unknown",
                ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"ERROR: unknown tool {name!r}",
                    is_error=True,
                ),
            )

        if not isinstance(args, dict):
            return _log(
                "bad_args",
                ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"ERROR: arguments must be an object, got {type(args).__name__}",
                    is_error=True,
                ),
                logged_args={},
            )

        # 1. jsonschema BEFORE execution (GUIA §B1).
        schema_error = validate_schema(tool.input_schema, args)
        if schema_error is not None:
            return _log(
                "schema_invalid",
                ToolResult(tool_call_id=tool_call_id, content=schema_error, is_error=True),
            )

        # 1b. D2 plugin veto: ANTES del permission gate. Solo puede ENDURECER
        # (invariante B4: policy nunca relaja) — devuelve un string de veto
        # → ToolResult honesto con decisión NUEVA append-only "plugin_denied".
        veto = self.hooks.fire_before_tool(name, args)
        if veto is not None:
            return _log(
                "plugin_denied",
                ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"ERROR: tool {name!r} vetada por plugin: {veto}",
                    is_error=True,
                ),
            )

        # 2. Permission gate (B4: Policy resuelve override+patrones+trifecta;
        # sin policy = permiso declarado del tool, semántica B1 intacta).
        declared = tool.permission
        effective = (
            self.policy.resolve(name, args, declared) if self.policy is not None else declared
        )
        if effective is Permission.DENY:
            if self.policy is not None and self.policy.plan_denied(name):
                # C5: error honesto específico del plan-mode (handoff §5).
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content=(
                        f"ERROR: tool {name!r} denegada — estás en PLAN-MODE "
                        "(solo exploración). Guarda el plan con save_plan y pide "
                        "aprobación con exit_plan_mode; al salir podrás ejecutar."
                    ),
                    is_error=True,
                )
            reason = "denied by policy" if effective is not declared else "is denied by policy"
            return _log(
                "deny",
                ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"ERROR: tool {name!r} {reason}",
                    is_error=True,
                ),
            )
        if effective is Permission.ASK:
            approved = False
            if self.approver is not None:
                try:
                    approved = await self.approver(name, args)
                except Exception as e:  # approver bugs must not kill the loop
                    return _log(
                        "ask_error",
                        ToolResult(
                            tool_call_id=tool_call_id,
                            content=f"ERROR: approval failed ({type(e).__name__}: {e})",
                            is_error=True,
                        ),
                    )
            if not approved:
                escalated = bool(
                    self.policy is not None
                    and self.policy.untrusted_seen
                    and declared is Permission.AUTO
                )
                why = (
                    "escalated to approval (untrusted content consumed)"
                    if escalated
                    else "requires approval and was not approved"
                )
                return _log(
                    "ask_escalated" if escalated else "ask_denied",
                    ToolResult(
                        tool_call_id=tool_call_id,
                        content=f"ERROR: tool {name!r} {why}",
                        is_error=True,
                    ),
                )

        # 3. Run — any exception becomes an honest error result.
        try:
            content = await tool.run(args)
            is_error = content.startswith("ERROR:")
        except Exception as e:
            # D2: on_error OBSERVA (plugins), el comportamiento no cambia —
            # la excepción sigue convirtiéndose en resultado honesto.
            self.hooks.fire_on_error(name, args, e)
            content = f"ERROR: tool {name} raised {type(e).__name__}: {e}"
            is_error = True
        content, truncated = truncate(content)
        # NIVEL 1a (dogfood #6): si el tool tocó un repo con AGENTS.md fuera
        # del cwd inicial, adjuntar sus reglas al result — mensaje NUEVO en la
        # conversación, el prefijo cacheable NO se toca (cache sagrada).
        if self.late_instructions is not None:
            reminder = self.late_instructions.reminder(name, args)
            if reminder:
                content += reminder
        # B4 trifecta: un tool que PRODUCE contenido no confiable (p.ej.
        # terminal con red) marca el resultado y la corrida entera.
        untrusted = bool(tool.produces_untrusted and not is_error)
        if untrusted and self.policy is not None:
            self.policy.mark_untrusted()
        decision = "ask_approved" if effective is Permission.ASK else "auto"
        return _log(
            decision,
            ToolResult(
                tool_call_id=tool_call_id,
                content=content,
                is_error=is_error,
                untrusted=untrusted,
                truncated=truncated,
            ),
        )
