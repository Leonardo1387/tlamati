"""T2 — Persistencia de compactación (circuito completo append-only).

Cierra el hallazgo del dogfooding 27-nov: la compactación disparaba en
runtime pero `record_summary` (store.py) no tenía ningún llamador y la tabla
`summaries` quedaba vacía → al retomar una sesión compactada el resumen se
perdía y el contexto se re-hinchaba con los mensajes crudos.

Diseño probado aquí (opción A del fundador):
1. `append_message` devuelve el seq asignado (lista paralela posición→seq).
2. El loop traduce el rango compactado a seqs de DB y llama `on_summary`.
3. `load_session` reconstruye: head crudo + marker de resumen + tail crudo;
   un resumen posterior ABSORBE al marker anterior (supersede).
4. La transcript cruda NUNCA se borra (append-only sagrado).
5. `LoopResult.history` trae la versión compactada (la TUI no re-infla en
   memoria entre corridas).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.context.compaction import CompactionConfig, Compactor
from tlamati.core.loop import LoopResult, run_loop
from tlamati.core.messages import (
    Message,
    MessageEnd,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.providers.base import ToolSpec
from tlamati.session.store import SessionStore
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry

SID = "20261127-t2-test"

BIG = "x" * 250


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    s = SessionStore(tmp_path / "sessions.db")
    assert s.broken is None, s.broken
    return s


# ---------------------------------------------------------------- nivel store


def test_append_message_returns_seq(store: SessionStore) -> None:
    store.create_session(SID)
    assert store.append_message(SID, Message(role="user", content="a")) == 0
    assert store.append_message(SID, Message(role="assistant", content="b")) == 1
    assert store.append_message(SID, Message(role="user", content="c")) == 2


def test_load_session_no_summaries_is_verbatim(store: SessionStore) -> None:
    """Sin summaries, load_session se comporta igual que antes (no regresión)."""
    store.create_session(SID)
    msgs = [Message(role="user", content=f"m{i}") for i in range(5)]
    for m in msgs:
        store.append_message(SID, m)
    loaded = store.load_session(SID)
    assert loaded is not None
    assert [m.content for m in loaded.messages] == [f"m{i}" for i in range(5)]
    assert loaded.history_seqs == [0, 1, 2, 3, 4]


def test_summary_replaces_range_on_load(store: SessionStore) -> None:
    """El circuito append-only: crudos siguen en messages; summaries gana la
    fila; load_session reconstruye head + marker + tail."""
    store.create_session(SID)
    for i in range(10):
        store.append_message(SID, Message(role="user", content=f"crudo-{i}"))
    # La compactación reemplazó [2, 6] por un resumen.
    store.record_summary(SID, 2, 6, "[CONTEXTO COMPACTADO — resumen] trabajo hecho", model="m")
    loaded = store.load_session(SID)
    assert loaded is not None
    contents = [m.content for m in loaded.messages]
    assert contents == [
        "crudo-0",
        "crudo-1",
        "[CONTEXTO COMPACTADO — resumen] trabajo hecho",
        "crudo-7",
        "crudo-8",
        "crudo-9",
    ]
    # seqs paralelos: el marker NO tiene seq (no vive en messages)
    assert loaded.history_seqs == [0, 1, None, 7, 8, 9]
    # append-only: los crudos siguen físicamente en la tabla
    db_rows = store.load_summaries(SID)
    assert len(db_rows) == 1
    assert db_rows[0]["from_seq"] == 2 and db_rows[0]["to_seq"] == 6


def test_second_summary_absorbs_previous_marker(store: SessionStore) -> None:
    """Dinámica real del loop: la 2ª compactación ve el marker anterior en su
    middle y lo absorbe — al reconstruir, solo sobrevive el último resumen."""
    store.create_session(SID)
    for i in range(14):
        store.append_message(SID, Message(role="user", content=f"crudo-{i}"))
    store.record_summary(SID, 2, 6, "RESUMEN-1", model="m")
    # segunda pasada: cubre desde el primer crudo post-marker hasta el 11;
    # su texto (generado por el modelo) ya incluye lo que decía RESUMEN-1.
    store.record_summary(SID, 7, 11, "RESUMEN-2 (incluye lo de antes)", model="m")
    loaded = store.load_session(SID)
    assert loaded is not None
    contents = [m.content for m in loaded.messages]
    assert "RESUMEN-1" not in contents
    assert contents == [
        "crudo-0",
        "crudo-1",
        "RESUMEN-2 (incluye lo de antes)",
        "crudo-12",
        "crudo-13",
    ]
    assert loaded.history_seqs == [0, 1, None, 12, 13]


# ------------------------------------------------- integración loop ↔ store


class _FakeSummarizer:
    def __init__(self, summary: str = "RESUMEN-T2") -> None:
        self.calls = 0

        async def summarize(transcript: str) -> tuple[str | None, Usage]:
            self.calls += 1
            return summary, Usage()

        self.summarize = summarize  # type: ignore[method-assign]


class LoopFakeProvider:
    """Turnos de read_file con _tick variable (el stall exacto ve progreso)."""

    model = "loop-fake"

    def __init__(self, tool_turns: int) -> None:
        self.turns_left = tool_turns
        self.calls: list[list[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Any]:
        self.calls.append(list(messages))
        if self.turns_left > 0:
            self.turns_left -= 1
            tid = f"c{len(self.calls)}"
            yield ToolCallStart(id=tid, name="read_file")
            yield ToolCallArgsDelta(
                id=tid, args_json=json.dumps({"path": "big.txt", "_tick": len(self.calls)})
            )
            yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))
        else:
            yield TextDelta(text="TERMINADO")
            yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))


@pytest.fixture
def big_workdir(tmp_path: Path) -> Path:
    (tmp_path / "big.txt").write_text("\n".join(f"line {i}: {BIG[:100]}" for i in range(10)))
    return tmp_path


class TestLoopPersistsCompaction:
    async def test_full_circuit_compact_persist_reload(
        self, store: SessionStore, big_workdir: Path
    ) -> None:
        """El test de integración pedido en T2 §4: compactar → persistir →
        recargar → el history recargado trae el resumen, NO los crudos del
        middle, y los crudos siguen en la tabla (append-only)."""
        store.create_session(SID)
        p = LoopFakeProvider(tool_turns=8)
        summaries: list[tuple[int, int, str]] = []
        n_persisted = 0

        def persist(m: Message) -> int | None:
            nonlocal n_persisted
            n_persisted += 1
            return store.append_message(SID, m)

        def persist_summary(f: int, t: int, text: str) -> None:
            summaries.append((f, t, text))
            store.record_summary(SID, f, t, text, model="fake")

        result: LoopResult = await run_loop(
            p,
            system="s",
            user_prompt="lee big.txt varias veces y termina",
            tools=Registry(make_tools(big_workdir)),
            budget=Budget(1500),
            max_turns=20,
            compactor=Compactor(
                CompactionConfig(retain_first=2, retain_recent=4, min_chars_to_clear=200),
                _FakeSummarizer(),
            ),
            on_message=persist,
            on_summary=persist_summary,
        )
        assert result.stop_reason == "end_turn"
        assert summaries, "el loop nunca avisó de un resumen persistible"
        from_seq, to_seq, text = summaries[0]
        assert text.startswith("[CONTEXTO COMPACTADO")
        assert from_seq <= to_seq
        # LoopResult.history trae la versión compactada y sus seqs paralelos
        assert len(result.history) == len(result.history_seqs)
        assert any(s is None for s in result.history_seqs)  # el marker no tiene seq
        assert len(result.history) < n_persisted  # history final < mensajes persistidos

        # Recargar: resume con resumen, no con el middle crudo.
        loaded = store.load_session(SID)
        assert loaded is not None
        assert any(m.content.startswith("[CONTEXTO COMPACTADO") for m in loaded.messages)
        assert len(loaded.messages) < n_persisted
        # los crudos siguen en la tabla messages (append-only intacto)
        assert store._db is not None
        raw_count = store._db.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id=?", (SID,)
        ).fetchone()[0]
        assert raw_count == n_persisted
        # y los seqs re-semillables alinean con los mensajes
        assert len(loaded.history_seqs) == len(loaded.messages)

    async def test_resume_seeded_history_keeps_seqs_aligned(
        self, store: SessionStore, big_workdir: Path
    ) -> None:
        """Retomar una sesión YA compactada y volver a correr: el loop siembra
        history_seqs y una segunda compactación sigue registrando rangos
        coherentes (from_seq <= to_seq y cubren mensajes reales)."""
        store.create_session(SID)
        for i in range(10):
            store.append_message(SID, Message(role="user", content=f"crudo-{i}"))
        store.record_summary(SID, 2, 6, "[CONTEXTO COMPACTADO — resumen] R1", model="fake")
        loaded = store.load_session(SID)
        assert loaded is not None

        summaries: list[tuple[int, int, str]] = []

        def persist(m: Message) -> int | None:
            return store.append_message(SID, m)

        def persist_summary(f: int, t: int, text: str) -> None:
            summaries.append((f, t, text))
            store.record_summary(SID, f, t, text, model="fake")

        p = LoopFakeProvider(tool_turns=8)
        result = await run_loop(
            p,
            system="s",
            user_prompt="sigue leyendo",
            tools=Registry(make_tools(big_workdir)),
            budget=Budget(1500),
            max_turns=20,
            compactor=Compactor(
                CompactionConfig(retain_first=2, retain_recent=4, min_chars_to_clear=200),
                _FakeSummarizer("RESUMEN-R2"),
            ),
            history=loaded.messages,
            history_seqs=loaded.history_seqs,
            on_message=persist,
            on_summary=persist_summary,
        )
        assert result.stop_reason == "end_turn"
        assert summaries, "segunda corrida con history sembrada no registró resumen"
        for f, t, _ in summaries:
            assert f <= t
            # los seqs citados existen en la tabla messages
            assert store._db is not None
            exists = store._db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id=? AND seq BETWEEN ? AND ?",
                (SID, f, t),
            ).fetchone()[0]
            assert exists == t - f + 1

    async def test_without_store_sinks_loop_still_works(self, big_workdir: Path) -> None:
        """Sin on_message/on_summary (headless --no-session), el loop compacta
        en memoria igual y LoopResult.history trae la versión compactada."""
        p = LoopFakeProvider(tool_turns=8)
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee",
            tools=Registry(make_tools(big_workdir)),
            budget=Budget(1500),
            max_turns=20,
            compactor=Compactor(
                CompactionConfig(retain_first=2, retain_recent=4, min_chars_to_clear=200),
                _FakeSummarizer(),
            ),
        )
        assert result.stop_reason == "end_turn"
        assert any(m.content.startswith("[CONTEXTO COMPACTADO") for m in result.history)
        assert result.history_seqs == [None] * len(result.history)
