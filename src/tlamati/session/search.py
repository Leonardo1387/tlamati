"""C7 — session_search: memoria episódica sobre el sessions.db existente.

Donor: hermes session_search (shape destilada, NO clonada — la versión hermes
es cara en acciones; aquí la regla del fundador manda: capability disponible,
output barato, cero re-dumps del transcript completo).

Diseño KISS:
- FTS5 si el sqlite lo trae (casi siempre); fallback honesto a LIKE.
- El índice se RECONSTRUYE en cada búsqueda (DELETE+INSERT SELECT sobre una
  DB local pequeña = ms): siempre fresco, cero maquinaria de sync/trigger.
- Output SIEMPRE truncado por diseño (snippets ±150 chars, slices por
  mensaje a 200 chars): buscar en el pasado no debe costar una fortuna en
  tokens — la lección del skill_view de 100K chars.
- Read-only: no toca messages/sessions, solo crea su tabla fts auxiliar.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from tlamati.tools.registry import Permission, Tool

SNIPPET_RADIUS = 150  # chars a cada lado del match
SLICE_MSG_CHARS = 200  # cada mensaje de un slice, truncado
MAX_DISCOVERY_SESSIONS = 3
MAX_SLICE_WINDOW = 10

_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    session_id UNINDEXED, seq UNINDEXED, role UNINDEXED, text
);
"""


def _extract_text(body_json: str) -> str:
    """Texto buscable de un mensaje: content + tool_result.content (si hay)."""
    import json

    try:
        d = json.loads(body_json)
    except ValueError:
        return body_json[:500]
    parts = [str(d.get("content") or "")]
    tr = d.get("tool_result") or {}
    if isinstance(tr, dict) and tr.get("content"):
        parts.append(str(tr["content"]))
    return "\n".join(p for p in parts if p)


class SessionSearch:
    """Búsquedas read-only sobre un sessions.db (misma DB que SessionStore)."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.broken: str | None = None
        self._fts = True

    def _connect(self) -> sqlite3.Connection | None:
        if not self.path.is_file():
            self.broken = f"{self.path} no existe (¿corrida sin --session?)"
            return None
        try:
            # read-write: el reindex FTS escribe su tabla auxiliar en la misma
            # DB (WAL permite concurrencia con el SessionStore de la corrida).
            return sqlite3.connect(self.path)
        except sqlite3.Error as e:
            self.broken = str(e)
            return None

    def _reindex(self, db: sqlite3.Connection) -> bool:
        """Reconstruye el índice FTS desde messages. False → usar LIKE."""
        if not self._fts:
            return False
        try:
            db.executescript(_FTS_DDL)
            db.execute("DELETE FROM messages_fts")
            # indexar texto EXTRAÍDO (no el JSON crudo): snippets limpios
            rows = db.execute("SELECT session_id, seq, role, body_json FROM messages").fetchall()
            db.executemany(
                "INSERT INTO messages_fts(session_id, seq, role, text) VALUES(?,?,?,?)",
                [(sid, seq, role, _extract_text(body)) for sid, seq, role, body in rows],
            )
            db.commit()  # sin commit el close() haría rollback del reindex
            return True
        except sqlite3.OperationalError:
            # sqlite sin FTS5 → degradación honesta a LIKE, nunca crash
            self._fts = False
            return False

    def _fts_query(self, raw: str) -> str:
        """Sanea la query del modelo a FTS5 básico: términos AND-eables."""
        terms = [t.strip('"') for t in raw.split() if t.strip('"')]
        return " ".join(f'"{t}"' for t in terms if t)

    def search(self, query: str, *, limit: int = MAX_DISCOVERY_SESSIONS) -> str:
        """Discovery: top sesiones con snippet del match. Barato por diseño."""
        db = self._connect()
        if db is None:
            return f"ERROR: {self.broken}"
        try:
            if self._reindex(db):
                rows = db.execute(
                    "SELECT session_id, seq, snippet(messages_fts, 3, '>>>', '<<<', '…', 24)"
                    " FROM messages_fts WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?",
                    (self._fts_query(query), 30),
                ).fetchall()
                hits: dict[str, list[tuple[int, str]]] = {}
                for sid, seq, snip in rows:
                    hits.setdefault(sid, []).append((int(seq), snip))
            else:
                like = f"%{query.split()[0]}%" if query.split() else "%"
                rows = db.execute(
                    "SELECT session_id, seq, substr(body_json,1,300) FROM messages"
                    " WHERE role IN ('user','assistant') AND body_json LIKE ? LIMIT 30",
                    (like,),
                ).fetchall()
                hits = {}
                for sid, seq, body in rows:
                    hits.setdefault(sid, []).append((int(seq), body))
            if not hits:
                return f"Sin resultados para {query!r}."
            # sesiones más recientes primero, máx `limit`
            metas = {}
            for sid in hits:
                m = db.execute(
                    "SELECT datetime(created_at,'unixepoch','localtime'), model,"
                    " substr(first_prompt,1,100) FROM sessions WHERE id=?",
                    (sid,),
                ).fetchone()
                metas[sid] = m or ("?", "?", "")
            out = [f"{len(hits)} sesión(es) con coincidencias (top {limit}):"]
            for sid in sorted(metas, key=lambda s: metas[s][0], reverse=True)[:limit]:
                when, model, prompt = metas[sid]
                out.append(
                    f"\n== {sid} | {when} | {model}\n   inicio: {str(prompt).replace(chr(10), ' ')}"
                )
                for seq, snip in sorted(hits[sid])[:3]:
                    clean = str(snip).replace("\n", " ")[: SNIPPET_RADIUS * 2]
                    out.append(f"   [seq {seq}] {clean}")
            out.append(
                "\nPara más contexto: session_search(session_id, around_seq) — "
                "devuelve una ventana corta, NUNCA la sesión completa."
            )
            return "\n".join(out)
        except sqlite3.Error as e:
            return f"ERROR de búsqueda: {e}"
        finally:
            db.close()

    def slice(self, session_id: str, *, around_seq: int | None = None, window: int = 5) -> str:
        """Slice de una sesión: ventana ±window mensajes, cada uno truncado."""
        db = self._connect()
        if db is None:
            return f"ERROR: {self.broken}"
        try:
            window = max(1, min(window, MAX_SLICE_WINDOW))
            if around_seq is None:
                rows = db.execute(
                    "SELECT seq, role, body_json FROM messages WHERE session_id=?"
                    " ORDER BY seq LIMIT ?",
                    (session_id, window * 2),
                ).fetchall()
                total = db.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id=?", (session_id,)
                ).fetchone()
                n = total[0] if total else 0
                if n == 0:
                    return f"ERROR: sesión {session_id!r} no existe o está vacía."
                head = f"Sesión {session_id}: primeros {len(rows)} de {n} mensajes.\n"
            else:
                rows = db.execute(
                    "SELECT seq, role, body_json FROM messages WHERE session_id=?"
                    " AND seq BETWEEN ? AND ? ORDER BY seq",
                    (session_id, around_seq - window, around_seq + window),
                ).fetchall()
                head = f"Sesión {session_id}: ventana ±{window} alrededor de seq {around_seq}.\n"
            out = [head]
            for seq, role, body in rows:
                text = _extract_text(body).replace("\n", " ")
                mark = ">>>" if around_seq is not None and int(seq) == around_seq else "   "
                out.append(f"{mark}[{seq}] {role}: {text[:SLICE_MSG_CHARS]}")
            return "\n".join(out)
        except sqlite3.Error as e:
            return f"ERROR: {e}"
        finally:
            db.close()


def make_session_search_tools(db_path: str | Path) -> list[Tool]:
    search = SessionSearch(db_path)

    async def run(args: dict[str, Any]) -> str:
        sid = str(args.get("session_id") or "").strip()
        if sid:
            around = args.get("around_seq")
            return search.slice(
                sid,
                around_seq=int(around) if around is not None else None,
                window=int(args.get("window") or 5),
            )
        query = str(args.get("query") or "").strip()
        if not query:
            return "ERROR: pasa query (búsqueda) o session_id (leer ventana)."
        return search.search(query, limit=int(args.get("limit") or MAX_DISCOVERY_SESSIONS))

    return [
        Tool(
            name="session_search",
            description=(
                "Buscar en sesiones PASADAS del usuario (memoria episódica local). "
                "Úsala solo cuando el usuario refiera trabajo anterior o preguntes "
                "'dónde dejamos X'. query → top sesiones con snippet; session_id "
                "(+around_seq opcional) → ventana corta de mensajes. Output barato: "
                "nunca devuelve sesiones completas."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "términos a buscar"},
                    "session_id": {"type": "string", "description": "leer una sesión"},
                    "around_seq": {"type": "integer", "description": "centro de la ventana"},
                    "window": {"type": "integer", "description": "±mensajes (máx 10)"},
                    "limit": {"type": "integer", "description": "máx sesiones (default 3)"},
                },
            },
            run=run,
            permission=Permission.AUTO,  # read-only sobre DB local
        ),
    ]
