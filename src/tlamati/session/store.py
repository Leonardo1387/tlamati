"""Session store — durable conversation history in SQLite (GUIA C1).

Local-first: every run persists its messages to a SQLite file (default
~/.local/share/tlamati/sessions.db) so a session can be resumed later
(`tlamati resume`, `--continue`). Donor semantics: Claude Code keeps only
local storage for session persistence (research/04 REA audit — no call-home
for transcripts); Tlamati does the same with a single append-friendly DB.

Schema is PREPARED for future compaction work (GUIA C1 destilada):
- messages.retention  — per-message flag: survives a window swap or not
  (donor: codex compact_retained_tool_outputs.rs).
- messages.content_cleared — microcompaction marker (donor: qwen
  microcompact.ts; honest eviction, never silent data loss).
- summaries — window→summary rows for budget compaction (donor: codex
  compact_token_budget.rs).

Design choices:
- stdlib sqlite3 (like policy/ledger.py), NOT aiosqlite: sessions are small,
  writes happen once per run at a message boundary, and zero new runtime
  deps keeps `uv tool install` honest. Deviation from GUIA C1 wording,
  approved rationale: consistency with the B5 ledger + no dep.
- A broken write sets self.broken and NEVER kills the run (ledger rule).
- Messages round-trip through Message.as_dict/from_dict (the narrow waist
  already defines serialization; store keeps the JSON blob verbatim).
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tlamati.core.messages import Message, Usage

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    last_active REAL NOT NULL,
    cwd TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    first_prompt TEXT NOT NULL DEFAULT '',
    stop_reason TEXT NOT NULL DEFAULT '',
    turns INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    body_json TEXT NOT NULL,
    retention INTEGER NOT NULL DEFAULT 1,
    content_cleared INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, seq)
);
CREATE TABLE IF NOT EXISTS usage (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    turn INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    PRIMARY KEY (session_id, turn)
);
CREATE TABLE IF NOT EXISTS summaries (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    from_seq INTEGER NOT NULL,
    to_seq INTEGER NOT NULL,
    summary TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    PRIMARY KEY (session_id, from_seq, to_seq)
);
"""


@dataclass(frozen=True)
class SessionInfo:
    """Row-level summary of one stored session (for `tlamati sessions`)."""

    id: str
    created_at: float
    last_active: float
    cwd: str
    model: str
    first_prompt: str
    stop_reason: str
    turns: int
    n_messages: int = 0

    def human(self) -> str:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(self.created_at))
        prompt = self.first_prompt.replace("\n", " ")[:60]
        return (
            f"{self.id}  {when}  turnos={self.turns}  stop={self.stop_reason or '?'}\n"
            f"    dir={self.cwd or '?'}  modelo={self.model or '?'}\n"
            f'    "{prompt}"'
        )


@dataclass
class StoredSession:
    """Everything needed to RESUME: messages + cumulative usage."""

    session_id: str
    messages: list[Message] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class SessionStore:
    """SQLite-backed session persistence. Sync API (stdlib sqlite3)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.broken: str | None = None
        self._db: sqlite3.Connection | None = None
        self._init_db()

    # -- lifecycle ----------------------------------------------------------

    def _init_db(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path)
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)
            db.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            db.commit()
            self._db = db
        except (sqlite3.Error, OSError) as e:
            self.broken = f"no se pudo abrir/crear {self.path}: {e}"
            self._db = None

    def close(self) -> None:
        if self._db is not None:
            with contextlib.suppress(sqlite3.Error):
                self._db.close()
            self._db = None

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor | None:
        """Write helper: broken DB degrades honestly, never raises into a run."""
        if self._db is None:
            return None
        try:
            cur = self._db.execute(sql, params)
            self._db.commit()
            return cur
        except sqlite3.Error as e:
            self.broken = f"write falló: {e}"
            self._db = None
            return None

    # -- sessions -----------------------------------------------------------

    def create_session(
        self, session_id: str, *, cwd: str = "", model: str = "", first_prompt: str = ""
    ) -> bool:
        now = time.time()
        cur = self._exec(
            "INSERT INTO sessions(id, created_at, last_active, cwd, model, first_prompt)"
            " VALUES(?,?,?,?,?,?)",
            (session_id, now, now, cwd, model, first_prompt),
        )
        return cur is not None

    def finish_session(self, session_id: str, *, stop_reason: str, turns: int) -> None:
        self._exec(
            "UPDATE sessions SET last_active=?, stop_reason=?, turns=? WHERE id=?",
            (time.time(), stop_reason, turns, session_id),
        )

    def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """Most recently active first."""
        if self._db is None:
            return []
        try:
            rows = self._db.execute(
                "SELECT s.id, s.created_at, s.last_active, s.cwd, s.model, s.first_prompt,"
                " s.stop_reason, s.turns, (SELECT COUNT(*) FROM messages m"
                "  WHERE m.session_id = s.id) AS n"
                " FROM sessions s ORDER BY s.last_active DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.Error as e:
            self.broken = f"read falló: {e}"
            return []
        return [
            SessionInfo(
                id=r[0],
                created_at=r[1],
                last_active=r[2],
                cwd=r[3],
                model=r[4],
                first_prompt=r[5],
                stop_reason=r[6],
                turns=r[7],
                n_messages=r[8],
            )
            for r in rows
        ]

    def latest_session_id(self) -> str | None:
        sessions = self.list_sessions(limit=1)
        return sessions[0].id if sessions else None

    def session_exists(self, session_id: str) -> bool:
        if self._db is None:
            return False
        try:
            row = self._db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone()
        except sqlite3.Error:
            return False
        return row is not None

    # -- messages -----------------------------------------------------------

    def append_message(
        self,
        session_id: str,
        message: Message,
        *,
        retention: bool = True,
        content_cleared: bool = False,
    ) -> None:
        cur = self._exec(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE session_id=?",
            (session_id,),
        )
        if cur is None:
            return
        try:
            seq = int(cur.fetchone()[0])
        except (TypeError, sqlite3.Error):
            self.broken = "no se pudo leer el próximo seq"
            return
        body = json.dumps(message.as_dict(), ensure_ascii=False, sort_keys=True)
        # Retention default (GUIA C1): tool results that are re-fetchable from
        # disk (read_file/search/skill_view output) could be retention=0 in a
        # future microcompaction pass; v1 keeps everything and lets the flag
        # exist. The microcompacted marker from A6 implies content already
        # cleared — record it honestly.
        cleared = content_cleared or (
            message.tool_result is not None and message.tool_result.microcompacted
        )
        self._exec(
            "INSERT INTO messages(session_id, seq, role, body_json, retention, content_cleared)"
            " VALUES(?,?,?,?,?,?)",
            (session_id, seq, message.role, body, int(retention), int(cleared)),
        )

    def append_messages(
        self, session_id: str, messages: list[Message], *, retention: bool = True
    ) -> None:
        for m in messages:
            self.append_message(session_id, m, retention=retention)

    def load_session(self, session_id: str) -> StoredSession | None:
        """Rebuild Message objects + cumulative usage for a resume."""
        if self._db is None:
            return None
        try:
            rows = self._db.execute(
                "SELECT body_json FROM messages WHERE session_id=? ORDER BY seq",
                (session_id,),
            ).fetchall()
            usage_rows = self._db.execute(
                "SELECT input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,"
                " cost_usd FROM usage WHERE session_id=? ORDER BY turn",
                (session_id,),
            ).fetchall()
        except sqlite3.Error as e:
            self.broken = f"load falló: {e}"
            return None
        messages: list[Message] = []
        for (body,) in rows:
            try:
                messages.append(Message.from_dict(json.loads(body)))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                # A corrupt row is skipped honestly, not fatal: resume degrades
                # with the rest of the conversation intact.
                messages.append(
                    Message(
                        role="user",
                        content=f"[mensaje corrupto omitido al cargar: {e}]",
                    )
                )
        usage = Usage()
        for r in usage_rows:
            usage = usage + Usage(
                input_tokens=r[0],
                output_tokens=r[1],
                cache_read_tokens=r[2],
                cache_write_tokens=r[3],
                cost_usd=r[4],
            )
        return StoredSession(session_id=session_id, messages=messages, usage=usage)

    # -- usage / summaries --------------------------------------------------

    def record_usage(self, session_id: str, turn: int, usage: Usage) -> None:
        self._exec(
            "INSERT OR REPLACE INTO usage(session_id, turn, input_tokens, output_tokens,"
            " cache_read_tokens, cache_write_tokens, cost_usd) VALUES(?,?,?,?,?,?,?)",
            (
                session_id,
                turn,
                usage.input_tokens,
                usage.output_tokens,
                usage.cache_read_tokens,
                usage.cache_write_tokens,
                usage.cost_usd,
            ),
        )

    def record_summary(
        self, session_id: str, from_seq: int, to_seq: int, summary: str, model: str = ""
    ) -> None:
        self._exec(
            "INSERT OR REPLACE INTO summaries(session_id, from_seq, to_seq, summary, model,"
            " created_at) VALUES(?,?,?,?,?,?)",
            (session_id, from_seq, to_seq, summary, model, time.time()),
        )

    def load_summaries(self, session_id: str) -> list[dict[str, Any]]:
        if self._db is None:
            return []
        try:
            rows = self._db.execute(
                "SELECT from_seq, to_seq, summary, model, created_at FROM summaries"
                " WHERE session_id=? ORDER BY from_seq",
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [
            {
                "from_seq": r[0],
                "to_seq": r[1],
                "summary": r[2],
                "model": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]
