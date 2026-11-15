"""Tests for evals/runner.py (A7) — descubrimiento de tareas, verificación y
JSONL, con FakeProvider: cero red. Las fixtures reales del repo son el input."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.evals.runner import DEFAULT_FIXTURES, TaskResult, _verify, discover_tasks, run_task
from tlamati.providers.base import ToolSpec

FIXTURE_NAMES = {"promedio", "offbyone", "conversor", "import_roto", "crear_modulo"}


class FixProvider:
    """Scripted provider: emite los tool calls que arreglan la tarea dada."""

    model = "fix-fake"

    def __init__(self, script: list[tuple[str, str, dict]]) -> None:
        self.script = script
        self.done = False

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        if self.done or not self.script:
            yield TextDelta(text="TERMINADO")
            yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))
            return
        self.done = True
        for tid, name, args in self.script:
            yield ToolCallStart(id=tid, name=name)
            yield ToolCallArgsDelta(id=tid, args_json=json.dumps(args))
        yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))


def test_discover_tasks_finds_five() -> None:
    tasks = discover_tasks(DEFAULT_FIXTURES)
    assert {t.name for t in tasks} == FIXTURE_NAMES


def test_discover_tasks_only_filter(tmp_path: Path) -> None:
    tasks = discover_tasks(DEFAULT_FIXTURES, "promedio")
    assert [t.name for t in tasks] == ["promedio"]
    assert discover_tasks(tmp_path) == []  # dir vacío → sin tareas


def test_seeds_all_fail_before_fix() -> None:
    """Invariante de fixture: cada semilla DEBE fallar sin el fix
    (si una pasa de entrada, la tarea no mide nada)."""
    for task in discover_tasks(DEFAULT_FIXTURES):
        ok, _ = _verify(task)
        assert not ok, f"{task.name} ya pasa sin arreglar — fixture inválida"


@pytest.mark.parametrize(
    ("task_name", "fixed_content"),
    [
        (
            "promedio",
            "def promedio(nums):\n    return sum(nums) / len(nums)\n",
        ),
        (
            "crear_modulo",
            "def suma_lista(nums):\n    return sum(nums)\n",
        ),
    ],
)
async def test_run_task_success_and_failure_paths(
    tmp_path: Path, task_name: str, fixed_content: str
) -> None:
    """Camino verde: el provider 'arregla' vía write_file → success=True.
    Camino rojo: provider que no hace nada → success=False con el output del verify."""
    task_dir = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == task_name)
    target_name = "calc.py" if task_name == "promedio" else "suma_lista.py"

    good = FixProvider([("c1", "write_file", {"path": target_name, "content": fixed_content})])
    r_ok = await run_task(task_dir, tmp_path / "ws", provider=good, max_turns=5, max_context=50_000)
    assert isinstance(r_ok, TaskResult)
    assert r_ok.success is True and r_ok.stop_reason == "end_turn"
    assert r_ok.turns == 2  # write_file + cierre end_turn
    assert r_ok.tokens_in == 20 and r_ok.tokens_out == 10  # Usage aditivo por turno
    assert r_ok.error is None

    lazy = FixProvider([])  # solo dice TERMINADO, no toca nada
    r_bad = await run_task(
        task_dir, tmp_path / "ws", provider=lazy, max_turns=5, max_context=50_000
    )
    assert r_bad.success is False
    assert r_bad.error and "FALLA" in r_bad.error  # output honesto del verifier


def test_task_result_serializes_to_jsonl() -> None:
    from dataclasses import asdict

    line = json.dumps(asdict(TaskResult(task="x", success=True)))
    parsed = json.loads(line)
    assert parsed["task"] == "x" and parsed["success"] is True
    assert "tokens_in" in parsed and "duration_s" in parsed  # schema del baseline
