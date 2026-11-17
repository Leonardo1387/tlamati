"""E2: headless --json — JSONL events + honest exit codes ($0, FakeProvider).

Técnica: monkeypatch de tlamati.cli.OpenAICompat → FakeProvider scripted
(mismo patrón que test_loop.py). Nada de red, nada de costo.
"""

from __future__ import annotations

import argparse
import io
import json
import os
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest

from tlamati.cli import _run_headless, build_parser
from tlamati.core.json_events import (
    EXIT_ABORTED,
    EXIT_BUDGET,
    EXIT_ERROR,
    EXIT_MAX_TOKENS,
    EXIT_MAX_TURNS,
    EXIT_OK,
    EXIT_REFUSAL,
    EXIT_USAGE,
    JsonlEmitter,
    exit_code_for,
)
from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCallStart,
    Usage,
)
from tlamati.providers.base import ToolSpec


class FakeProvider:
    """Scripted provider (patrón test_loop.py): cada stream() consume un turno."""

    model = "fake"

    def __init__(self, turns: list[list[tuple[Any, ...]]]) -> None:
        self.turns = turns

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        script = self.turns.pop(0) if self.turns else [("text", "fin")]
        has_tools = False
        for step in script:
            if step[0] == "text":
                yield TextDelta(text=str(step[1]))
            elif step[0] == "tool":
                has_tools = True
                yield ToolCallStart(id=str(step[1]), name=str(step[2]))
        yield MessageEnd(
            stop_reason="tool_use" if has_tools else "end_turn",
            usage=Usage(input_tokens=10, output_tokens=5),
        )


class _FakeOpenAICompat(FakeProvider):
    """Reemplazo de OpenAICompat en cli.py: misma firma de constructor."""

    _script: ClassVar[list[list[tuple[Any, ...]]]] = [[("text", "TERMINADO")]]

    def __init__(self, model: str = "", base_url: str = "", api_key: str = "") -> None:
        super().__init__(list(self._script))


@pytest.fixture(autouse=True)
def _fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tlamati.cli.OpenAICompat", _FakeOpenAICompat)
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")


def _json_args(extra: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(["-p", "haz algo", "--json", *extra])


def _parse_jsonl(out: str) -> list[dict[str, Any]]:
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]  # cada línea DEBE ser JSON válido


class TestExitCodeMap:
    @pytest.mark.parametrize(
        ("reason", "code"),
        [
            ("end_turn", EXIT_OK),
            ("max_turns", EXIT_MAX_TURNS),
            ("budget_exceeded", EXIT_BUDGET),
            ("error", EXIT_ERROR),
            ("aborted", EXIT_ABORTED),
            ("refusal", EXIT_REFUSAL),
            ("max_tokens", EXIT_MAX_TOKENS),
        ],
    )
    def test_known_reasons(self, reason: str, code: int) -> None:
        assert exit_code_for(reason) == code

    def test_unknown_reason_fails_closed(self) -> None:
        # Razón desconocida NUNCA mapea a éxito (misma filosofía que policy).
        assert exit_code_for("motivo_misterioso") == EXIT_ERROR

    def test_usage_code_reserved_for_argparse(self) -> None:
        assert EXIT_USAGE == 2


class TestJsonStream:
    async def test_happy_path_stream_and_rc(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _FakeOpenAICompat._script = [[("text", "TERMINADO ok")]]
        monkeypatch.chdir(os.environ.get("TMPDIR", "/tmp"))
        rc = await _run_headless(_json_args(["--no-session", "--no-audit", "--no-memory"]))
        assert rc == 0
        events = _parse_jsonl(capsys.readouterr().out)
        kinds = [e["event"] for e in events]
        assert kinds[0] == "init"
        assert kinds[-1] == "result"
        assert "text" in kinds
        final = events[-1]
        assert final["stop_reason"] == "end_turn"
        assert final["exit_code"] == 0
        assert final["usage"]["input_tokens"] == 10
        assert final["final_text"] == "TERMINADO ok"
        # Todo evento lleva ts + event (contrato del stream).
        assert all("ts" in e and "event" in e for e in events)

    async def test_tool_events_visible(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "dato.txt").write_text("hola\n")
        monkeypatch.chdir(tmp_path)
        _FakeOpenAICompat._script = [
            [("tool", "t1", "read_file", {"path": "dato.txt"})],
            [("text", "leído")],
        ]
        rc = await _run_headless(_json_args(["--no-session", "--no-audit", "--no-memory"]))
        assert rc == 0
        kinds = [e["event"] for e in _parse_jsonl(capsys.readouterr().out)]
        # tool_start (stream) + tool_run + tool_result (ejecución real).
        for esperado in ("tool_start", "tool_run", "tool_result", "turn_end"):
            assert esperado in kinds

    async def test_missing_api_key_emits_error_event(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
        rc = await _run_headless(_json_args([]))
        assert rc == EXIT_USAGE
        events = _parse_jsonl(capsys.readouterr().out)
        assert [e["event"] for e in events] == ["init", "error"]
        assert "API key" in events[-1]["message"]

    async def test_human_mode_unchanged_no_json_on_stdout(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sin --json: stdout humano (texto plano), NO JSONL — contrato viejo intacto.
        _FakeOpenAICompat._script = [[("text", "TERMINADO")]]
        monkeypatch.chdir(os.environ.get("TMPDIR", "/tmp"))
        args = build_parser().parse_args(
            ["-p", "x", "--no-session", "--no-audit", "--no-memory", "--quiet"]
        )
        rc = await _run_headless(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "{" not in out  # ningún JSON se coló en el modo humano


class TestEmitterFailSoft:
    def test_broken_stream_degrades_silently(self) -> None:
        class _Broken(io.TextIOBase):
            def write(self, s: str) -> int:
                raise BrokenPipeError(32, "Broken pipe")

        em = JsonlEmitter(stream=cast(Any, _Broken()))
        em.emit("text", {"text": "x"})  # NO debe lanzar
        assert em.broken is not None and "BrokenPipeError" in em.broken
        em.emit("result", {})  # emisiones posteriores = no-op
