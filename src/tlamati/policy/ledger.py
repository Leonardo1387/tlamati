"""B5 — policy/ledger.py: libro de auditoría SQLite append-only.

Cada ejecución de tool queda registrada (GUIA §B5): turno, tool, args,
decisión de permiso, hash sha256 del resultado, is_error/untrusted/truncated.
El costo por turno lo registra el consumidor vía ``record_turn_cost`` (el CLI
lo alimenta del evento ``turn_end`` del loop — el core no conoce el ledger).

Invariantes:
- APPEND-ONLY: solo INSERT. Sin UPDATE/DELETE en la API (auditoría honesta).
- SIN dependencias nuevas: sqlite3 stdlib (aiosqlite llega en C1 para la
  session store; los writes del ledger son pequeños y síncronos).
- Fallo del ledger NUNCA rompe la corrida: un write roto se traga y se
  reporta por la marca ``broken`` (degradación honesta, no silencio).
- El hash es del contenido EXACTO post-truncado que volvió al modelo.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    session_id TEXT NOT NULL,
    turn       INTEGER NOT NULL,
    tool       TEXT NOT NULL,
    args_json  TEXT NOT NULL,
    decision   TEXT NOT NULL,
    result_sha256 TEXT,
    is_error   INTEGER NOT NULL DEFAULT 0,
    untrusted  INTEGER NOT NULL DEFAULT 0,
    truncated  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS turn_costs (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    session_id TEXT NOT NULL,
    turn       INTEGER NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read    INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL
);
CREATE INDEX IF NOT EXISTS idx_tool_events_session ON tool_events(session_id);
CREATE INDEX IF NOT EXISTS idx_turn_costs_session ON turn_costs(session_id);
"""


@dataclass(frozen=True)
class ToolEvent:
    """Fila leída de tool_events (para `tlamati audit`)."""

    seq: int
    ts: float
    turn: int
    tool: str
    args_json: str
    decision: str
    result_sha256: str | None
    is_error: bool
    untrusted: bool
    truncated: bool


@dataclass(frozen=True)
class TurnCost:
    seq: int
    ts: float
    turn: int
    input_tokens: int
    output_tokens: int
    cache_read: int
    cost_usd: float | None


class Ledger:
    """Auditoría append-only. ``turn`` lo avanza el consumidor (CLI)."""

    def __init__(self, db_path: Path, session_id: str) -> None:
        self.db_path = db_path
        self.session_id = session_id
        self.turn = 0
        self.broken: str | None = None  # motivo si un write falló (honesto)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def record_tool_event(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        decision: str,
        result_content: str | None = None,
        is_error: bool = False,
        untrusted: bool = False,
        truncated: bool = False,
    ) -> None:
        digest = (
            hashlib.sha256(result_content.encode("utf-8", errors="replace")).hexdigest()
            if result_content is not None
            else None
        )
        try:
            self._conn.execute(
                "INSERT INTO tool_events (ts, session_id, turn, tool, args_json, decision,"
                " result_sha256, is_error, untrusted, truncated)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    self.session_id,
                    self.turn,
                    tool,
                    json.dumps(args, ensure_ascii=False, sort_keys=True),
                    decision,
                    digest,
                    int(is_error),
                    int(untrusted),
                    int(truncated),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as e:  # la auditoría no mata la corrida
            self.broken = f"{type(e).__name__}: {e}"

    def record_turn_cost(
        self,
        *,
        turn: int,
        input_tokens: int,
        output_tokens: int,
        cache_read: int,
        cost_usd: float | None,
    ) -> None:
        try:
            self._conn.execute(
                "INSERT INTO turn_costs (ts, session_id, turn, input_tokens, output_tokens,"
                " cache_read, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    self.session_id,
                    turn,
                    input_tokens,
                    output_tokens,
                    cache_read,
                    cost_usd,
                ),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            self.broken = f"{type(e).__name__}: {e}"

    def close(self) -> None:
        self._conn.close()

    # ---- lectura (solo SELECT; usado por `tlamati audit`) ----

    @staticmethod
    def read_session(db_path: Path, session_id: str) -> tuple[list[ToolEvent], list[TurnCost]]:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            events = [
                ToolEvent(
                    seq=r[0],
                    ts=r[1],
                    turn=r[2],
                    tool=r[3],
                    args_json=r[4],
                    decision=r[5],
                    result_sha256=r[6],
                    is_error=bool(r[7]),
                    untrusted=bool(r[8]),
                    truncated=bool(r[9]),
                )
                for r in conn.execute(
                    "SELECT seq, ts, turn, tool, args_json, decision, result_sha256,"
                    " is_error, untrusted, truncated FROM tool_events"
                    " WHERE session_id = ? ORDER BY seq",
                    (session_id,),
                )
            ]
            costs = [
                TurnCost(
                    seq=r[0],
                    ts=r[1],
                    turn=r[2],
                    input_tokens=r[3],
                    output_tokens=r[4],
                    cache_read=r[5],
                    cost_usd=r[6],
                )
                for r in conn.execute(
                    "SELECT seq, ts, turn, input_tokens, output_tokens, cache_read, cost_usd"
                    " FROM turn_costs WHERE session_id = ? ORDER BY seq",
                    (session_id,),
                )
            ]
            return events, costs
        finally:
            conn.close()

    @staticmethod
    def list_sessions(db_path: Path) -> list[tuple[str, int, float]]:
        """(session_id, n_eventos, último ts) por sesión, más reciente primero."""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return [
                (r[0], r[1], r[2])
                for r in conn.execute(
                    "SELECT session_id, COUNT(*), MAX(ts) FROM tool_events"
                    " GROUP BY session_id ORDER BY MAX(ts) DESC"
                )
            ]
        finally:
            conn.close()
