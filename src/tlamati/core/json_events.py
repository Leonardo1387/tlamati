"""E2: JSONL event stream for headless `--json` (the agent as a CI citizen).

Contrato (GUIA E2, donor hermes-agent: honest exit codes + JSONL events):
- stdout es EXCLUSIVO del stream JSONL: un objeto JSON por línea, cada uno con
  `ts` (epoch float), `event` (tipo) y payload plano. Stderr queda humano.
- El evento final SIEMPRE es `result` con stop_reason, usage y exit_code —
  el consumidor de CI no necesita parsear nada más para decidir.
- Exit codes honestos: cada stop_reason tiene su código; un stop_reason
  desconocido NUNCA mapea a éxito (falla cerrado, misma filosofía que la
  escalera de permisos).

Vocabulario de eventos (emitidos por run_loop vía on_event + el CLI):
  init, text, tool_start, tool_run, tool_result, turn_end, budget,
  compaction, error, result
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, TextIO

from tlamati.core.loop import LoopResult
from tlamati.core.messages import Usage

# Exit codes honestos (contrato CLI de E2). 2 queda reservado a argparse/uso
# (fail-fast de arranque: sin api key, config inválida, flags excluyentes).
EXIT_OK = 0  # end_turn: el agente terminó su trabajo
EXIT_MAX_TURNS = 1  # se agotaron los turnos (tarea incompleta, no es error)
EXIT_USAGE = 2  # mal uso / arranque fallido
EXIT_BUDGET = 3  # presupuesto de contexto excedido
EXIT_ERROR = 4  # error de provider o del loop
EXIT_ABORTED = 5  # abortado por el usuario (SIGINT x2)
EXIT_REFUSAL = 6  # el modelo se rehusó
EXIT_MAX_TOKENS = 7  # tope de tokens de salida alcanzado

_EXIT_BY_REASON: dict[str, int] = {
    "end_turn": EXIT_OK,
    "max_turns": EXIT_MAX_TURNS,
    "budget_exceeded": EXIT_BUDGET,
    "error": EXIT_ERROR,
    "aborted": EXIT_ABORTED,
    "refusal": EXIT_REFUSAL,
    "max_tokens": EXIT_MAX_TOKENS,
}


def exit_code_for(stop_reason: str) -> int:
    """stop_reason → exit code. Razón desconocida = EXIT_ERROR (fail-closed:
    nunca afirmar éxito ante algo que no entendemos)."""
    return _EXIT_BY_REASON.get(stop_reason, EXIT_ERROR)


def usage_to_dict(usage: Usage) -> dict[str, Any]:
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "cost_usd": usage.cost_usd,
    }


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    """Los eventos del loop pueden traer Usage (dataclass) — el resto del
    payload ya es plano. `default=str` en dumps es el cinturón de seguridad
    para tipos inesperados (Path, etc.): el stream NUNCA se rompe por un tipo."""
    return {k: (usage_to_dict(v) if isinstance(v, Usage) else v) for k, v in data.items()}


@dataclass
class JsonlEmitter:
    """Escribe un objeto JSON por línea. Fail-soft: un stdout roto (EPIPE,
    consumidor cerrado) degrada en silencio — la corrida importa más que el
    stream (misma lección que el ledger B5)."""

    stream: TextIO = field(default_factory=lambda: sys.stdout)
    broken: str | None = None

    def emit(self, kind: str, data: dict[str, Any]) -> None:
        if self.broken is not None:
            return
        line = {"ts": round(time.time(), 3), "event": kind, **_jsonable(data)}
        try:
            self.stream.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
            self.stream.flush()
        except (BrokenPipeError, OSError) as e:
            self.broken = f"{type(e).__name__}: {e}"

    def emit_error(self, stage: str, message: str) -> None:
        self.emit("error", {"stage": stage, "message": message})


def result_event(result: LoopResult, *, session_id: str | None, model: str) -> dict[str, Any]:
    """El evento `result` final — todo lo que un consumidor de CI necesita."""
    return {
        "final_text": result.final_text,
        "stop_reason": result.stop_reason,
        "turns": result.turns,
        "usage": usage_to_dict(result.usage),
        "error": result.error,
        "session_id": session_id,
        "model": model,
        "exit_code": exit_code_for(result.stop_reason),
    }
