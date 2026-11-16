"""Tests for session/store.py (C1)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from tlamati.core.messages import Message, ToolCall, ToolResult, Usage
from tlamati.session.store import SessionStore

SID = "20261116-174500-abc12345"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SessionStore]:
    s = SessionStore(tmp_path / "sessions.db")
    assert s.broken is None, s.broken
    yield s
    s.close()


def test_create_and_list(store: SessionStore) -> None:
    assert store.create_session(SID, cwd="/repo", model="qwen/qwen3-coder", first_prompt="hola")
    sessions = store.list_sessions()
    assert len(sessions) == 1
    info = sessions[0]
    assert info.id == SID
    assert info.cwd == "/repo"
    assert info.model == "qwen/qwen3-coder"
    assert info.first_prompt == "hola"
    assert info.n_messages == 0
    assert store.session_exists(SID)
    assert not store.session_exists("nope")


def test_duplicate_id_is_broken_not_raise(store: SessionStore) -> None:
    assert store.create_session(SID)
    assert not store.create_session(SID)  # UNIQUE constraint → honest False
    assert store.broken is not None


def test_message_roundtrip_preserves_narrow_waist(store: SessionStore) -> None:
    store.create_session(SID)
    msgs = [
        Message(role="user", content="arregla el bug", id="msg_u1"),
        Message(
            role="assistant",
            content="voy a leer",
            id="msg_a1",
            tool_calls=(
                ToolCall(
                    id="tc1",
                    name="read_file",
                    arguments={"path": "x.py"},
                    raw_arguments='{"path": "x.py"}',
                ),
            ),
        ),
        Message(
            role="tool",
            tool_result=ToolResult(
                tool_call_id="tc1", content="def f(): ...", is_error=False, untrusted=False
            ),
            id="msg_t1",
        ),
    ]
    store.append_messages(SID, msgs)
    loaded = store.load_session(SID)
    assert loaded is not None
    assert len(loaded.messages) == 3
    assert loaded.messages[0] == msgs[0]
    assert loaded.messages[1] == msgs[1]
    assert loaded.messages[2] == msgs[2]


def test_microcompacted_result_records_content_cleared(store: SessionStore) -> None:
    store.create_session(SID)
    m = Message(
        role="tool",
        tool_result=ToolResult(
            tool_call_id="tc9",
            content="[Old tool result content cleared]",
            microcompacted=True,
        ),
    )
    store.append_message(SID, m)
    loaded = store.load_session(SID)
    assert loaded is not None
    # The flag is honest: the stored row says content was cleared.
    assert loaded.messages[0].tool_result is not None
    assert loaded.messages[0].tool_result.microcompacted is True


def test_usage_accumulates_across_turns(store: SessionStore) -> None:
    store.create_session(SID)
    store.record_usage(SID, 1, Usage(input_tokens=100, output_tokens=10, cache_read_tokens=80))
    store.record_usage(SID, 2, Usage(input_tokens=200, output_tokens=20, cost_usd=0.01))
    loaded = store.load_session(SID)
    assert loaded is not None
    assert loaded.usage.input_tokens == 300
    assert loaded.usage.output_tokens == 30
    assert loaded.usage.cache_read_tokens == 80
    assert loaded.usage.cost_usd == pytest.approx(0.01)


def test_finish_session_records_stop_and_turns(store: SessionStore) -> None:
    store.create_session(SID, first_prompt="tarea")
    store.finish_session(SID, stop_reason="end_turn", turns=4)
    info = store.list_sessions()[0]
    assert info.stop_reason == "end_turn"
    assert info.turns == 4


def test_latest_session_id(store: SessionStore) -> None:
    assert store.latest_session_id() is None
    store.create_session("s1")
    store.create_session("s2")
    # touch s1 so it becomes the most recent
    store.finish_session("s1", stop_reason="end_turn", turns=1)
    assert store.latest_session_id() == "s1"


def test_summary_roundtrip(store: SessionStore) -> None:
    store.create_session(SID)
    store.record_summary(SID, 0, 9, "El usuario pidió arreglar X; se hizo Y.", model="cheap")
    rows = store.load_summaries(SID)
    assert len(rows) == 1
    assert rows[0]["from_seq"] == 0
    assert rows[0]["to_seq"] == 9
    assert "arreglar X" in rows[0]["summary"]
    assert rows[0]["model"] == "cheap"


def test_broken_db_degrades_honestly(tmp_path: Path) -> None:
    # Point the store at a path that is NOT a directory → init fails.
    blocker = tmp_path / "blocker"
    blocker.write_text("no soy un directorio")
    s = SessionStore(blocker / "sessions.db")
    assert s.broken is not None
    # Every operation degrades instead of raising.
    assert not s.create_session(SID)
    assert s.list_sessions() == []
    assert s.latest_session_id() is None
    assert s.load_session(SID) is None
    s.append_message(SID, Message(role="user", content="x"))  # no raise
    s.record_usage(SID, 1, Usage())  # no raise
    s.close()


def test_corrupt_row_skipped_honestly(store: SessionStore) -> None:
    store.create_session(SID)
    store.append_message(SID, Message(role="user", content="uno", id="m1"))
    # Corrupt the stored JSON directly (simulates disk damage).
    db = store._db
    assert db is not None
    db.execute(
        "UPDATE messages SET body_json=? WHERE session_id=? AND seq=0",
        ("{roto", SID),
    )
    db.commit()
    store.append_message(SID, Message(role="user", content="dos", id="m2"))
    loaded = store.load_session(SID)
    assert loaded is not None
    assert len(loaded.messages) == 2
    assert "corrupto" in loaded.messages[0].content
    assert loaded.messages[1].content == "dos"


def test_wal_mode_and_schema_version(tmp_path: Path) -> None:
    s = SessionStore(tmp_path / "sessions.db")
    db = s._db
    assert db is not None
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    assert version == "1"
    s.close()


def test_body_json_is_sorted_keys_stable(store: SessionStore) -> None:
    """Cache-stability prep: the stored blob must be byte-stable for equal
    messages (sorted keys), so future diff/ratchet checks are reliable."""
    store.create_session(SID)
    m = Message(role="user", content="x", id="m1")
    store.append_message(SID, m)
    db = store._db
    assert db is not None
    raw = db.execute("SELECT body_json FROM messages WHERE session_id=?", (SID,)).fetchone()[0]
    expected = json.dumps(m.as_dict(), ensure_ascii=False, sort_keys=True)
    assert raw == expected


# ---------------------------------------------------------------------------
# Integration: run_loop persists via on_message and resumes via history ($0,
# scripted provider — no LLM).
# ---------------------------------------------------------------------------

from collections.abc import AsyncIterator, Sequence  # noqa: E402

from tlamati.context.budget import Budget  # noqa: E402
from tlamati.core.loop import run_loop  # noqa: E402
from tlamati.core.messages import (  # noqa: E402
    Event,
    MessageEnd,
    TextDelta,
)
from tlamati.providers.base import ToolSpec  # noqa: E402
from tlamati.tools.builtin import make_tools  # noqa: E402
from tlamati.tools.registry import Registry  # noqa: E402


class ScriptProvider:
    """Minimal scripted provider: one text turn per call."""

    model = "fake"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.seen: list[list[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.seen.append(list(messages))
        reply = self.replies.pop(0) if self.replies else "fin"
        yield TextDelta(text=reply)
        yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))


async def test_run_loop_persists_and_resumes(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "s.db")
    assert store.broken is None
    sid = "s-int-1"
    store.create_session(sid, first_prompt="primer mensaje")
    registry = Registry(make_tools(tmp_path, sandbox=False))
    budget = Budget(max_context_tokens=128_000)

    # Run 1: persists every message via on_message.
    p1 = ScriptProvider(["respuesta uno"])
    r1 = await run_loop(
        p1,
        system="sys",
        user_prompt="primer mensaje",
        tools=registry,
        budget=budget,
        on_message=lambda m: store.append_message(sid, m),
    )
    assert r1.stop_reason == "end_turn"
    store.record_usage(sid, r1.turns, r1.usage)
    store.finish_session(sid, stop_reason=r1.stop_reason, turns=r1.turns)

    loaded = store.load_session(sid)
    assert loaded is not None
    assert [m.role for m in loaded.messages] == ["user", "assistant"]
    assert loaded.messages[1].content == "respuesta uno"

    # Run 2: RESUME — history seeds the conversation; provider must see it.
    p2 = ScriptProvider(["respuesta dos"])
    r2 = await run_loop(
        p2,
        system="sys",
        user_prompt="segundo mensaje",
        tools=registry,
        budget=Budget(max_context_tokens=128_000),
        history=loaded.messages,
        on_message=lambda m: store.append_message(sid, m),
    )
    assert r2.stop_reason == "end_turn"
    # The provider saw the resumed history: sys + 2 previos + nuevo user.
    seen = p2.seen[0]
    assert seen[0].role == "system"
    assert seen[1].content == "primer mensaje"
    assert seen[2].content == "respuesta uno"
    assert seen[3].content == "segundo mensaje"

    final = store.load_session(sid)
    assert final is not None
    assert len(final.messages) == 4
    store.close()
