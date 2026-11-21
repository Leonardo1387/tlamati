"""Tests for session/search.py (C7 — memoria episódica).

Patrón del archivo hermano (test_session_store.py): SessionStore real sobre
tmp_path, cero red, cero LLM. La búsqueda se ejercita tanto por la clase
(SessionSearch) como por la tool (make_session_search_tools → run async).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tlamati.core.messages import Message
from tlamati.session.search import SessionSearch, make_session_search_tools
from tlamati.session.store import SessionStore

SID = "20261120-235900-feedbeef"
SID2 = "20261121-100000-cafe1234"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """DB poblada: 2 sesiones, mensajes distinguibles por contenido."""
    s = SessionStore(tmp_path / "sessions.db")
    assert s.broken is None, s.broken
    s.create_session(SID, model="qwen/qwen3-coder", first_prompt="arregla el bug del scroll")
    s.append_messages(
        SID,
        [
            Message(role="user", content="el scroll del TUI no respeta mi posición", id="u1"),
            Message(role="assistant", content="voy a mirar app.py", id="a1"),
            Message(role="assistant", content="arreglado con follow-tail", id="a2"),
        ],
    )
    s.create_session(SID2, model="nvidia/nemotron", first_prompt="proyecto puente latam")
    s.append_messages(
        SID2,
        [Message(role="user", content="crea la carpeta de boolanga", id="u2")],
    )
    s.close()
    return tmp_path / "sessions.db"


def test_discovery_finds_session_with_snippet(db_path: Path) -> None:
    out = SessionSearch(db_path).search("scroll")
    assert SID in out
    assert "scroll" in out.lower()
    assert "qwen3-coder" in out  # metadata de la sesión


def test_discovery_ranks_only_matching_sessions(db_path: Path) -> None:
    out = SessionSearch(db_path).search("boolanga")
    assert SID2 in out
    assert SID not in out  # la otra sesión no menciona boolanga


def test_no_results_is_honest(db_path: Path) -> None:
    out = SessionSearch(db_path).search("palabraquenadieescribio")
    assert "Sin resultados" in out


def test_slice_window_centered_on_seq(db_path: Path) -> None:
    out = SessionSearch(db_path).slice(SID, around_seq=1, window=1)
    assert ">>>" in out  # el mensaje ancla va marcado
    assert "voy a mirar" in out
    assert "no respeta" in out


def test_slice_unknown_session_is_error(db_path: Path) -> None:
    out = SessionSearch(db_path).slice("no-existe")
    assert "ERROR" in out


def test_missing_db_is_error_not_crash(tmp_path: Path) -> None:
    out = SessionSearch(tmp_path / "nada.db").search("x")
    assert "ERROR" in out and "no existe" in out


def test_like_fallback_when_fts_unavailable(db_path: Path) -> None:
    # Degradación honesta: sqlite sin FTS5 → LIKE, mismo contrato de salida.
    ss = SessionSearch(db_path)
    ss._fts = False
    out = ss.search("boolanga")
    assert SID2 in out


async def test_tool_query_and_session_id_shapes(db_path: Path) -> None:
    (tool,) = make_session_search_tools(db_path)
    assert tool.name == "session_search"
    # shape discovery
    res = await tool.run({"query": "scroll"})
    assert SID in res
    # shape slice
    res = await tool.run({"session_id": SID, "around_seq": 0, "window": 2})
    assert "no respeta" in res
    # sin query ni session_id → error honesto, no excepción
    res = await tool.run({})
    assert "ERROR" in res


def test_output_is_bounded(db_path: Path) -> None:
    """Regla del fundador: buscar en el pasado NO debe costar una fortuna."""
    out = SessionSearch(db_path).search("el", limit=3)
    assert len(out) < 5_000  # snippets truncados por diseño
