"""Tests for context/compaction.py (A6) — M2 microcompaction, cheap-model
summary with fallback chain, and the golden rule: the cacheable prefix
(system + head anchor) survives compaction byte-stable. Zero network."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.context.compaction import (
    CLEARED_PLACEHOLDER,
    CompactionConfig,
    Compactor,
    ModelSummarizer,
    microcompact,
    render_for_summary,
)
from tlamati.core.loop import run_loop
from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCall,
    ToolCallArgsDelta,
    ToolCallStart,
    ToolResult,
    Usage,
)
from tlamati.providers.base import ProviderError, ToolSpec
from tlamati.tools_min.mini import make_tools

BIG = "x" * 600  # ~150+ tokens por tool result


def _assistant_call(cid: str, name: str, args: dict[str, Any]) -> Message:
    return Message(
        role="assistant",
        content="",
        tool_calls=(ToolCall(id=cid, name=name, arguments=args, raw_arguments=json.dumps(args)),),
    )


def _tool_msg(cid: str, content: str, *, is_error: bool = False) -> Message:
    return Message(
        role="tool", tool_result=ToolResult(tool_call_id=cid, content=content, is_error=is_error)
    )


def _history(n_reads: int, tool: str = "read_file") -> list[Message]:
    """user prompt + n (assistant call + tool result) pares."""
    h = [Message(role="user", content="arregla el bug")]
    for i in range(n_reads):
        h.append(_assistant_call(f"c{i}", tool, {"path": "a.py"}))
        h.append(_tool_msg(f"c{i}", f"{i}|{BIG}"))
    return h


CFG = CompactionConfig(
    retain_first=2, retain_recent=2, min_summary_target=2, min_chars_to_clear=100
)


class FakeSummarizer:
    """Summarizer protocol double: canned text or total failure."""

    def __init__(self, summary: str | None = "RESUMEN-X") -> None:
        self.summary = summary
        self.calls: list[str] = []

    async def summarize(self, transcript: str) -> tuple[str | None, Usage]:
        self.calls.append(transcript)
        return self.summary, Usage(input_tokens=100, output_tokens=10)


class _SummaryProvider:
    """Provider double for ModelSummarizer: canned summary text."""

    model = "cheap-fake"

    def __init__(self, text: str = "RESUMEN-BARATO") -> None:
        self.text = text
        self.calls = 0

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.calls += 1
        yield TextDelta(text=self.text)
        yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=50, output_tokens=7))


class _DeadProvider:
    model = "dead"

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        raise ProviderError("boom", kind="http", retryable=True, status=500)
        yield  # pragma: no cover


# ---------------------------------------------------------------------------
# M2 microcompaction
# ---------------------------------------------------------------------------


class TestMicrocompact:
    def test_clears_old_keeps_recent(self) -> None:
        h = _history(6)  # 13 mensajes: cutoff = max(2, 13-2) = 11
        out, cleared = microcompact(h, CFG)
        assert cleared == 5  # tool results viejos (índices < 11) limpiados
        # los 2 últimos mensajes (tail) intactos
        assert out[-1] is h[-1] and out[-2] is h[-2]
        for m in out[:11]:
            if m.role == "tool":
                assert m.tool_result is not None
                assert m.tool_result.content == CLEARED_PLACEHOLDER
                assert m.tool_result.microcompacted is True

    def test_skips_errors_small_and_non_whitelist(self) -> None:
        h = [
            Message(role="user", content="p"),
            _assistant_call("c1", "read_file", {}),
            _tool_msg("c1", "ERROR: boom", is_error=True),  # error → nunca
            _assistant_call("c2", "read_file", {}),
            _tool_msg("c2", "corto"),  # < min_chars_to_clear → nunca
            _assistant_call("c3", "herramienta_secreta", {}),
            _tool_msg("c3", f"9|{BIG}"),  # fuera del whitelist → nunca
        ]
        out, cleared = microcompact(h, CompactionConfig(retain_first=0, retain_recent=0,
                                                        min_chars_to_clear=100))
        assert cleared == 0
        assert out == h

    def test_idempotent_and_anti_collision(self) -> None:
        h = _history(6)
        once, cleared1 = microcompact(h, CFG)
        twice, cleared2 = microcompact(once, CFG)
        assert cleared1 == 5 and cleared2 == 0  # segunda pasada: nada que hacer
        assert twice == once
        # anti-colisión: texto de usuario que EMPIEZA como el placeholder no es marcador
        tricky = Message(role="user", content=CLEARED_PLACEHOLDER[:-1] + " y además algo más")
        out3, cleared3 = microcompact([tricky], CompactionConfig(retain_first=0, retain_recent=0))
        assert cleared3 == 0 and out3[0] is tricky


# ---------------------------------------------------------------------------
# ModelSummarizer (fallback chain)
# ---------------------------------------------------------------------------


class TestModelSummarizer:
    async def test_fallback_chain_skips_dead_model(self) -> None:
        good = _SummaryProvider("RESUMEN-DEL-BUENO")
        s = ModelSummarizer([_DeadProvider(), good])
        summary, usage = await s.summarize("transcript")
        assert summary == "RESUMEN-DEL-BUENO"
        assert usage.output_tokens == 7
        assert good.calls == 1

    async def test_all_fail_returns_none(self) -> None:
        s = ModelSummarizer([_DeadProvider(), _DeadProvider()])
        summary, _ = await s.summarize("transcript")
        assert summary is None


# ---------------------------------------------------------------------------
# Compactor (pass completo: M2 + resumen / ventana nueva)
# ---------------------------------------------------------------------------


class TestCompactor:
    async def test_summary_replaces_middle_only(self) -> None:
        h = _history(6)
        head = [m.as_dict() for m in h[: CFG.retain_first]]
        tail = [m.as_dict() for m in h[-CFG.retain_recent :]]
        budget = Budget(100_000)
        comp = Compactor(CFG, FakeSummarizer("RESUMEN-X"))
        out, report = await comp.compact(
            h, system="s", tools=(), budget=budget, status="exceeded"
        )
        assert report is not None
        assert report.summarized == len(h) - CFG.retain_first - CFG.retain_recent
        assert report.tokens_after < report.tokens_before
        # head anchor y tail sobreviven BYTE-STABLE (regla de oro)
        assert [m.as_dict() for m in out[: CFG.retain_first]] == head
        assert [m.as_dict() for m in out[-CFG.retain_recent :]] == tail
        assert any(
            m.role == "user" and m.content.startswith("[CONTEXTO COMPACTADO") for m in out
        )
        assert "RESUMEN-X" in next(
            m.content for m in out if m.content.startswith("[CONTEXTO COMPACTADO")
        )

    async def test_window_drop_when_summary_fails(self) -> None:
        h = _history(6)
        comp = Compactor(CFG, FakeSummarizer(None))  # cadena agotada
        out, report = await comp.compact(
            h, system="s", tools=(), budget=Budget(100_000), status="exceeded"
        )
        assert report is not None and report.summary_failed is True
        marker = next(
            m.content for m in out if m.content.startswith("[COMPACTACIÓN DE EMERGENCIA]")
        )
        assert "descartaron" in marker  # degradación HONESTA, nunca silenciosa

    async def test_warn_only_microcompacts_no_model_call(self) -> None:
        h = _history(6)
        fake = FakeSummarizer()
        comp = Compactor(CFG, fake)
        _out, report = await comp.compact(
            h, system="s", tools=(), budget=Budget(100_000), status="warn"
        )
        assert fake.calls == []  # en warn no se gasta modelo
        assert report is not None and report.summarized == 0 and report.microcompacted == 5

    async def test_noop_returns_none_report(self) -> None:
        h = [Message(role="user", content="hola")]
        comp = Compactor(CFG, FakeSummarizer())
        out, report = await comp.compact(
            h, system="s", tools=(), budget=Budget(100_000), status="warn"
        )
        assert report is None and out == h


def test_render_for_summary_includes_names_and_paths() -> None:
    h = _history(2)
    text = render_for_summary(h)
    assert "read_file" in text and "a.py" in text and "[tool_result" in text


# ---------------------------------------------------------------------------
# Integración con el loop: sesión larga sintética (entregable A-1d del HANDOFF)
# ---------------------------------------------------------------------------


class LoopFakeProvider:
    """Muchos turnos de lectura → fuerza el budget a warn/exceeded varias veces."""

    model = "loop-fake"

    def __init__(self, tool_turns: int) -> None:
        self.turns_left = tool_turns
        self.calls: list[list[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.calls.append(list(messages))
        if self.turns_left > 0:
            self.turns_left -= 1
            tid = f"c{len(self.calls)}"
            yield ToolCallStart(id=tid, name="read_file")
            yield ToolCallArgsDelta(id=tid, args_json=json.dumps({"path": "big.txt"}))
            yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))
        else:
            yield TextDelta(text="TERMINADO")
            yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))


@pytest.fixture
def big_workdir(tmp_path: Path) -> Path:
    # ~300 tokens por lectura: suficiente para inflar el history en 8 turnos,
    # pero la cola retenida cabe en el budget tras compactar.
    (tmp_path / "big.txt").write_text("\n".join(f"line {i}: {BIG[:100]}" for i in range(10)))
    return tmp_path


class TestLoopCompaction:
    async def test_long_session_compacts_without_breaking_cache(self, big_workdir: Path) -> None:
        p = LoopFakeProvider(tool_turns=8)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee big.txt varias veces y termina",
            tools=make_tools(big_workdir),
            budget=Budget(750),  # tan apretado que M2 no basta → exceeded → resumen
            max_turns=20,
            on_event=lambda k, d: events.append((k, d)),
            compactor=Compactor(
                CompactionConfig(retain_first=2, retain_recent=4, min_chars_to_clear=200),
                FakeSummarizer("RESUMEN: se leyó big.txt varias veces."),
            ),
        )
        assert result.stop_reason == "end_turn"
        compactions = [d for k, d in events if k == "compaction"]
        assert compactions, "el loop nunca disparó compaction en una sesión larga"
        assert any(c["summarized"] > 0 for c in compactions)
        assert any(c["microcompacted"] > 0 for c in compactions)
        assert all(c["tokens_after"] < c["tokens_before"] for c in compactions)

        # REGLA DE ORO: en TODA llamada al proveedor, el prefijo cacheable
        # (system + head anchor) es byte-estable en lo que viaja por la red.
        # Nota: el loop crea un Message(role="system") NUEVO por llamada — su
        # id interno difiere, pero los adapters serializan role+content, así
        # que comparamos sin id (lo que ve el gateway de caché).
        def wire(m: Message) -> dict[str, Any]:
            d = m.as_dict()
            d.pop("id")
            return d

        first_full = next(c for c in p.calls if len(c) >= 3)
        for call in p.calls:
            assert wire(call[0]) == wire(first_full[0])  # system
            assert wire(call[1]) == wire(first_full[1])  # user prompt
            if len(call) >= 3:
                assert wire(call[2]) == wire(first_full[2])  # primera respuesta assistant

        # el resumen entró como marcador visible en alguna llamada posterior
        assert any(
            m.content.startswith("[CONTEXTO COMPACTADO")
            for call in p.calls
            for m in call
        )
        # los tool results viejos quedaron con placeholder + flag de auditoría
        assert any(
            m.role == "tool"
            and m.tool_result is not None
            and m.tool_result.microcompacted
            and m.tool_result.content == CLEARED_PLACEHOLDER
            for call in p.calls
            for m in call
        )

    async def test_no_compactor_keeps_old_behavior(self, big_workdir: Path) -> None:
        """Sin compactor, budget_exceeded sigue parando el loop (no regresión)."""
        p = LoopFakeProvider(tool_turns=8)
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee big.txt",
            tools=make_tools(big_workdir),
            budget=Budget(1_600),
            max_turns=20,
        )
        assert result.stop_reason == "budget_exceeded"
