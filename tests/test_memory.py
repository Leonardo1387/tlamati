"""Tests for C2 memory: store caps + batch atomicity, tools, auto-dream."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tlamati.core.messages import Message, ToolCall, ToolResult, Usage
from tlamati.memory import store as store_mod
from tlamati.memory.dream import dream, parse_dream_output, transcript_from_messages
from tlamati.memory.store import (
    MemoryError,
    MemoryStore,
    project_memory_dir,
    seed_if_empty,
)
from tlamati.memory.tools import make_memory_tools


@pytest.fixture
def mem(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "memory")


class TestMemoryStore:
    def test_seed_creates_both_files(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        assert mem.memory_path.is_file()
        assert mem.user_path.is_file()
        assert "consolida" in mem.memory_path.read_text().lower()

    def test_add_and_load(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        stats = mem.apply_batch(
            "memory", [{"action": "add", "content": "El proyecto usa pytest con asyncio auto"}]
        )
        assert stats.entries == 1
        mf = mem.load("memory")
        assert "pytest" in mf.entries[0]

    def test_replace_and_remove_by_old_text(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        mem.apply_batch("memory", [{"action": "add", "content": "dato viejo sobre X"}])
        mem.apply_batch(
            "memory",
            [{"action": "replace", "old_text": "dato viejo", "content": "dato nuevo sobre X"}],
        )
        mf = mem.load("memory")
        assert mf.entries == ("dato nuevo sobre X",)
        mem.apply_batch("memory", [{"action": "remove", "old_text": "dato nuevo"}])
        assert mem.load("memory").entries == ()

    def test_batch_atomic_all_or_nothing(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        mem.apply_batch("memory", [{"action": "add", "content": "entrada uno"}])
        # Second op fails (old_text not found) → file must be UNTOUCHED.
        with pytest.raises(MemoryError):
            mem.apply_batch(
                "memory",
                [
                    {"action": "add", "content": "entrada dos"},
                    {"action": "remove", "old_text": "no existe"},
                ],
            )
        entries = mem.load("memory").entries
        assert entries == ("entrada uno",)

    def test_cap_entries_rejects_with_consolidation_hint(
        self, mem: MemoryStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed_if_empty(mem)
        monkeypatch.setattr(store_mod, "MAX_ENTRIES", 2)
        mem.apply_batch(
            "memory",
            [{"action": "add", "content": "a"}, {"action": "add", "content": "b"}],
        )
        with pytest.raises(MemoryError, match="consolida"):
            mem.apply_batch("memory", [{"action": "add", "content": "c"}])
        # File unchanged: still 2 entries.
        assert len(mem.load("memory").entries) == 2

    def test_batch_can_free_room_and_add(
        self, mem: MemoryStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point of atomic batches: consolidate + add in ONE call."""
        seed_if_empty(mem)
        monkeypatch.setattr(store_mod, "MAX_ENTRIES", 2)
        mem.apply_batch(
            "memory",
            [{"action": "add", "content": "a"}, {"action": "add", "content": "b"}],
        )
        stats = mem.apply_batch(
            "memory",
            [
                {"action": "remove", "old_text": "a"},
                {"action": "add", "content": "c"},
            ],
        )
        assert stats.entries == 2
        assert mem.load("memory").entries == ("b", "c")

    def test_ambiguous_old_text_rejected(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        mem.apply_batch(
            "memory",
            [{"action": "add", "content": "x uno"}, {"action": "add", "content": "x dos"}],
        )
        with pytest.raises(MemoryError, match="ambiguo"):
            mem.apply_batch("memory", [{"action": "remove", "old_text": "x"}])

    def test_old_text_not_found_suggests_closest(self, mem: MemoryStore) -> None:
        """T6 (17% de los errores reales): old_text mal transcrito → el error
        devuelve la entrada más parecida en vez de fallo seco."""
        seed_if_empty(mem)
        mem.apply_batch(
            "memory",
            [{"action": "add", "content": "El usuario prefiere respuestas concisas y directas"}],
        )
        with pytest.raises(MemoryError, match="entrada más parecida") as exc:
            mem.apply_batch(
                "memory",
                [
                    {
                        "action": "replace",
                        "old_text": "El usuario prefiere respuestas concisas y diretas",  # typo
                        "content": "otra cosa",
                    }
                ],
            )
        assert "concisas y directas" in str(exc.value)
        # El archivo queda intacto (semántica atómica preservada).
        assert mem.load("memory").entries == ("El usuario prefiere respuestas concisas y directas",)

    def test_old_text_not_found_sin_candidato_fallo_seco(self, mem: MemoryStore) -> None:
        """Sin candidato ≥0.6 NO se inventa sugerencia (nunca ruido)."""
        seed_if_empty(mem)
        mem.apply_batch("memory", [{"action": "add", "content": "entrada sobre perros"}])
        with pytest.raises(MemoryError) as exc:
            mem.apply_batch("memory", [{"action": "remove", "old_text": "zzz qqq www inexistente"}])
        assert "old_text no encontrado" in str(exc.value)
        assert "entrada más parecida" not in str(exc.value)
        assert mem.load("memory").entries == ("entrada sobre perros",)

    def test_sugerencia_no_cambia_atomicidad_del_batch(self, mem: MemoryStore) -> None:
        """T6: la sugerencia es solo texto del error; el batch atómico sigue
        siendo all-or-nothing (op 1 válida + op 2 fallida → nada aplica)."""
        seed_if_empty(mem)
        mem.apply_batch("memory", [{"action": "add", "content": "entrada uno sobre gatos"}])
        with pytest.raises(MemoryError, match="entrada más parecida"):
            mem.apply_batch(
                "memory",
                [
                    {"action": "add", "content": "entrada dos"},
                    # similar pero NO substring → no matchea → sugerencia
                    {"action": "remove", "old_text": "entrada una sobre gatos"},
                ],
            )
        # op[0] (add) NO aplicó porque op[1] falló: todo o nada.
        assert mem.load("memory").entries == ("entrada uno sobre gatos",)

    def test_invalid_target(self, mem: MemoryStore) -> None:
        with pytest.raises(MemoryError, match="target inválido"):
            mem.load("equipo")

    def test_render_for_prompt_stable_and_only_changed_by_edits(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        r1 = mem.render_for_prompt()
        assert r1 == ""  # empty files inject nothing (prefix stays byte-stable)
        mem.apply_batch("memory", [{"action": "add", "content": "hecho"}])
        r2 = mem.render_for_prompt()
        assert "hecho" in r2
        assert mem.render_for_prompt() == r2  # idempotent read

    def test_project_scope_path(self, tmp_path: Path) -> None:
        assert project_memory_dir(tmp_path) == tmp_path / ".tlamati" / "memory"


class TestMemoryTools:
    async def test_memory_tool_add(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        tools = make_memory_tools(mem)
        mem_tool = next(t for t in tools if t.name == "memory")
        out = await mem_tool.run(
            {"target": "user", "operations": [{"action": "add", "content": "prefiere español"}]}
        )
        assert out.startswith("OK")
        assert "1/100" in out

    async def test_memory_tool_error_is_honest_and_nonfatal(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        tools = make_memory_tools(mem)
        mem_tool = next(t for t in tools if t.name == "memory")
        out = await mem_tool.run(
            {"target": "memory", "operations": [{"action": "remove", "old_text": "nada"}]}
        )
        assert out.startswith("ERROR")
        assert "NO fue modificado" in out

    async def test_search_memory(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        mem.apply_batch("memory", [{"action": "add", "content": "El deploy usa Acme"}])
        mem.apply_batch("user", [{"action": "add", "content": "Usuario prefiere terminal"}])
        tools = make_memory_tools(mem)
        search = next(t for t in tools if t.name == "search_memory")
        out = await search.run({"query": "acme", "target": "all"})
        assert "[memory]" in out and "Acme" in out
        out2 = await search.run({"query": "zzz"})
        assert "sin coincidencias" in out2

    async def test_memory_tool_is_auto_permission(self, mem: MemoryStore) -> None:
        from tlamati.tools.registry import Permission

        tools = make_memory_tools(mem)
        for t in tools:
            assert t.permission == Permission.AUTO
            assert not t.produces_untrusted  # local files, no egress → no trifecta


class _FakeSummarizer:
    def __init__(self, reply: str | None) -> None:
        self.reply = reply
        self.calls: list[str] = []

    async def summarize(self, transcript: str) -> tuple[str | None, Usage]:
        self.calls.append(transcript)
        return self.reply, Usage(input_tokens=5, output_tokens=5)


def _session_messages() -> list[Message]:
    return [
        Message(
            role="user",
            content=(
                "Recuerda que el deploy de este proyecto se hace con Acme "
                "y el repo es privado. " * 3
            ),
        ),
        Message(
            role="assistant",
            content="ok",
            tool_calls=(ToolCall(id="t1", name="terminal", arguments={"command": "ls"}),),
        ),
        Message(role="tool", tool_result=ToolResult(tool_call_id="t1", content="src tests")),
    ]


class TestAutoDream:
    async def test_dream_applies_operations(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        fake = _FakeSummarizer(
            '{"operations": [{"target": "memory", "action": "add",'
            ' "content": "Deploy del proyecto vía Acme"}]}'
        )
        report = await dream(mem, fake, _session_messages())
        assert report.applied == 1
        assert "Acme" in mem.load("memory").entries[0]

    async def test_dream_replies_with_fences_and_prose(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        fake = _FakeSummarizer(
            'Claro, aquí está:\n```json\n{"operations": [{"target": "user",'
            ' "action": "add", "content": "Habla español"}]}\n```'
        )
        report = await dream(mem, fake, _session_messages())
        assert report.applied == 1
        assert "español" in mem.load("user").entries[0]

    async def test_dream_empty_ops_is_honest_noop(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        fake = _FakeSummarizer('{"operations": []}')
        report = await dream(mem, fake, _session_messages())
        assert report.applied == 0
        assert report.skipped_reason is not None

    async def test_dream_model_failure_never_raises(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        fake = _FakeSummarizer(None)  # chain failed
        report = await dream(mem, fake, _session_messages())
        assert report.applied == 0
        assert "vacío" in (report.skipped_reason or "")

    async def test_dream_caps_respected(
        self, mem: MemoryStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed_if_empty(mem)
        monkeypatch.setattr(store_mod, "MAX_ENTRIES", 1)
        fake = _FakeSummarizer(
            '{"operations": [{"target": "memory", "action": "add", "content": "uno"},'
            ' {"target": "memory", "action": "add", "content": "dos"}]}'
        )
        report = await dream(mem, fake, _session_messages())
        assert report.applied == 1  # second rejected by cap
        assert len(mem.load("memory").entries) == 1

    async def test_dream_short_session_skipped(self, mem: MemoryStore) -> None:
        seed_if_empty(mem)
        fake = _FakeSummarizer('{"operations": []}')
        report = await dream(mem, fake, [Message(role="user", content="hola")])
        assert "corta" in (report.skipped_reason or "")
        assert fake.calls == []  # never spent a model call

    def test_parse_dream_output_garbage_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_dream_output("no json aquí")
        with pytest.raises(ValueError):
            parse_dream_output('{"sin_operations": 1}')

    def test_parse_dream_output_caps_at_five(self) -> None:
        ops = [{"action": "add", "content": f"e{i}"} for i in range(10)]
        import json as _json

        parsed, gaps = parse_dream_output(_json.dumps({"operations": ops}))
        assert len(parsed) == 5
        assert gaps == []  # G2: sin campo "gaps" → lista vacía tolerante

    def test_transcript_truncates_tool_bodies(self) -> None:
        msgs = _session_messages()
        t: Any = transcript_from_messages(msgs)
        assert "tool usó" not in t
        assert "terminal" in t
        assert len(t) <= 40_000
