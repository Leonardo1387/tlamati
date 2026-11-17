"""Plugin INTERNO de auditoría (D2): migración real de Registry._log (B5).

La auditoría NO es opcional (B5) — este plugin se registra SIEMPRE que el
Registry recibe un ledger; no es descubrible ni desactivable. El registro de
tool_events vive aquí como consumidor concreto #1 del hook ``after_tool``
(prueba real del mecanismo: los tests B5 siguen verdes SIN cambios).

``turn_costs`` NO está aquí: es un evento del loop (turn_end), no de tool —
sigue en el _ledger_wrapper del CLI (no inventar un 4º hook, regla
anti-speculative).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tlamati.core.messages import ToolResult
    from tlamati.plugins import HookRegistry
    from tlamati.policy.ledger import Ledger


def register_ledger_hooks(hooks: HookRegistry, ledger: Ledger) -> None:
    """Registra el after_tool que escribe tool_events (semántica B5 exacta:
    record_tool_event ya degrada honesto si el ledger está roto)."""

    def _after_tool(name: str, args: dict[str, Any], decision: str, result: ToolResult) -> None:
        ledger.record_tool_event(
            tool=name,
            args=args,
            decision=decision,
            result_content=result.content,
            is_error=result.is_error,
            untrusted=result.untrusted,
            truncated=result.truncated,
        )

    hooks.add_after_tool(_after_tool)
