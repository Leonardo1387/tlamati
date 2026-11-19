"""E3c: fix trampa plan-mode headless.

Reproducción del bug de la run2 (19-nov): en headless SIN --plan-mode el arnés
ofrecía enter/exit_plan_mode; el modelo entraba solo a plan-mode y quedaba
ENCERRADO (exit_plan_mode es fail-closed sin aprobador humano, regla de oro
C5) quemando los 50 turnos. Fix: no ofrecer la puerta sin salida.

Invariantes ($0, FakeProvider):
1. headless sin --plan-mode → plan tools AUSENTES del tool_list y bloque
   PLAN_MODE_PROMPT ausente del system prompt (prefijo veraz).
2. headless con --plan-mode → plan tools presentes + bloque presente.
3. La regla de oro NO se relaja: con --plan-mode y sin aprobador,
   exit_plan_mode sigue fallando cerrado (cubierto en test_plan_mode.py;
   aquí verificamos que las tools expuestas son las mismas de siempre).
4. Prefijo byte-estable DENTRO del mismo modo (cache sagrada).
"""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import ClassVar

import pytest

from tlamati.cli import _run_headless, build_parser
from tlamati.core.messages import Event, Message, MessageEnd, TextDelta, Usage
from tlamati.plan.mode import PLAN_MODE_PROMPT
from tlamati.plan.tools import make_plan_tools
from tlamati.providers.base import ToolSpec

PLAN_TOOL_NAMES = {"enter_plan_mode", "exit_plan_mode", "save_plan"}


class _CapturingProvider:
    """FakeProvider que captura system prompt y tool specs de cada turno."""

    captured_systems: ClassVar[list[str]] = []
    captured_tools: ClassVar[list[list[ToolSpec]]] = []

    model = "fake"

    def __init__(self, model: str = "", base_url: str = "", api_key: str = "") -> None:
        pass

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        for m in messages:
            if m.role == "system" and isinstance(m.content, str):
                _CapturingProvider.captured_systems.append(m.content)
        _CapturingProvider.captured_tools.append(list(tools))
        yield TextDelta(text="fin")
        yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=1, output_tokens=1))


@pytest.fixture(autouse=True)
def _fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _CapturingProvider.captured_systems = []
    _CapturingProvider.captured_tools = []
    monkeypatch.setattr("tlamati.cli.OpenAICompat", _CapturingProvider)
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")
    monkeypatch.chdir(tmp_path)


def _args(extra: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(["-p", "haz algo", *extra])


def _tool_names(specs: Sequence[ToolSpec]) -> set[str]:
    return {s.name for s in specs}


class TestPlanToolsNotOfferedHeadless:
    async def test_sin_plan_mode_tools_ausentes(self) -> None:
        rc = await _run_headless(_args(["--no-session", "--no-audit", "--no-memory"]))
        assert rc == 0
        names = _tool_names(_CapturingProvider.captured_tools[0])
        assert not (names & PLAN_TOOL_NAMES), "la puerta sin salida sigue ofreciéndose"
        assert "enter_plan_mode" not in _CapturingProvider.captured_systems[0]

    async def test_sin_plan_mode_bloque_prompt_ausente(self) -> None:
        await _run_headless(_args(["--no-session", "--no-audit", "--no-memory"]))
        system = _CapturingProvider.captured_systems[0]
        assert PLAN_MODE_PROMPT.strip()[:40] not in system
        assert "PLAN-MODE" not in system  # prefijo veraz: no anuncia lo que no existe

    async def test_con_plan_mode_tools_presentes(self) -> None:
        extra = ["--plan-mode", "--no-session", "--no-audit", "--no-memory"]
        rc = await _run_headless(_args(extra))
        assert rc == 0
        names = _tool_names(_CapturingProvider.captured_tools[0])
        assert names >= PLAN_TOOL_NAMES
        assert "PLAN-MODE" in _CapturingProvider.captured_systems[0]


class TestGoldenRuleNotRelaxed:
    def test_las_tools_ofrecidas_son_las_mismas(self, tmp_path: Path) -> None:
        # El fix retira la OFERTA, no la protección: make_plan_tools con
        # plan_approver=None conserva exit fail-closed (ver test_plan_mode.py).
        from tlamati.plan.mode import PlanState

        tools = make_plan_tools(tmp_path, PlanState(active=True), plan_approver=None)
        assert {t.name for t in tools} == PLAN_TOOL_NAMES


class TestPrefixStableWithinMode:
    async def test_dos_corridas_mismo_modo_prefijo_identico(self) -> None:
        await _run_headless(_args(["--no-session", "--no-audit", "--no-memory"]))
        await _run_headless(_args(["--no-session", "--no-audit", "--no-memory"]))
        s1, s2 = _CapturingProvider.captured_systems[0], _CapturingProvider.captured_systems[1]
        assert s1 == s2  # cache sagrada: byte-idéntico dentro del mismo modo
        t1, t2 = _CapturingProvider.captured_tools[0], _CapturingProvider.captured_tools[1]
        assert [s.name for s in t1] == [s.name for s in t2]
