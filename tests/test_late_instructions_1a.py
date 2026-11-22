"""NIVEL 1a — inyección tardía de AGENTS.md (dogfood #6).

Fixture de regresión del handoff: el agente arranca FUERA del repo, edita un
archivo dentro de un repo cuyo AGENTS.md dice "escribe BANANA" → las reglas
DEBEN llegar al contexto (tool result), sin mutar el prefijo del sistema.

Determinista: FakeProvider scripted (patrón test_loop.py), cero LLM, cero red.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.late_instructions import LateInstructions
from tlamati.tools.registry import Registry, Tool


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    return root


@pytest.fixture
def home_dir(tmp_path: Path) -> Path:
    d = tmp_path / "home"
    d.mkdir()
    return d


class TestReminderUnit:
    def test_sin_repo_silencio(self, home_dir: Path, tmp_path: Path) -> None:
        """Un path fuera de todo repo no genera recordatorio (advisory)."""
        li = LateInstructions(home_dir)
        assert li.reminder("write_file", {"path": str(tmp_path / "libre.txt")}) is None

    def test_repo_con_agents_md_genera_recordatorio(self, repo: Path, home_dir: Path) -> None:
        (repo / "AGENTS.md").write_text(
            "SIEMPRE escribe la palabra BANANA en tu respuesta final", encoding="utf-8"
        )
        li = LateInstructions(home_dir)
        texto = li.reminder("write_file", {"path": str(repo / "a.txt")})
        assert texto is not None
        assert "BANANA" in texto
        assert "system-reminder" in texto

    def test_repo_sin_agents_md_silencio(self, repo: Path, home_dir: Path) -> None:
        li = LateInstructions(home_dir)
        assert li.reminder("edit", {"path": str(repo / "a.txt")}) is None

    def test_dedup_por_version(self, repo: Path, home_dir: Path) -> None:
        (repo / "AGENTS.md").write_text("regla v1", encoding="utf-8")
        li = LateInstructions(home_dir)
        first = li.reminder("write_file", {"path": str(repo / "a.txt")})
        second = li.reminder("write_file", {"path": str(repo / "b.txt")})
        assert first is not None
        assert second is None  # misma versión → una sola inyección por corrida

    def test_cambio_de_contenido_reinyecta(self, repo: Path, home_dir: Path) -> None:
        f = repo / "AGENTS.md"
        f.write_text("regla v1", encoding="utf-8")
        li = LateInstructions(home_dir)
        assert li.reminder("write_file", {"path": str(repo / "a.txt")}) is not None
        f.write_text("regla v2", encoding="utf-8")
        texto = li.reminder("write_file", {"path": str(repo / "b.txt")})
        assert texto is not None and "regla v2" in texto

    def test_version_en_prefijo_no_se_duplica(self, repo: Path) -> None:
        """Sesión arrancada DENTRO del repo: C4 ya inyectó esa versión →
        la inyección tardía permanece en silencio."""
        from tlamati.context.instructions import load_instructions

        (repo / "AGENTS.md").write_text("regla del prefijo", encoding="utf-8")
        prefix_v = load_instructions(repo, include_global=False).version
        li = LateInstructions(repo, prefix_versions=frozenset({prefix_v}))
        assert li.reminder("edit", {"path": str(repo / "a.txt")}) is None

    def test_terminal_cd_detecta_repo(self, repo: Path, home_dir: Path) -> None:
        (repo / "AGENTS.md").write_text("regla cd", encoding="utf-8")
        li = LateInstructions(home_dir)
        texto = li.reminder("terminal", {"command": f"cd {repo} && git status"})
        assert texto is not None and "regla cd" in texto

    def test_terminal_sin_cd_silencio(self, home_dir: Path) -> None:
        li = LateInstructions(home_dir)
        assert li.reminder("terminal", {"command": "ls -la"}) is None

    def test_tool_no_tocador_silencio(self, repo: Path, home_dir: Path) -> None:
        """read_file NO 'toca' el repo según el handoff → sin recordatorio."""
        (repo / "AGENTS.md").write_text("regla", encoding="utf-8")
        li = LateInstructions(home_dir)
        assert li.reminder("read_file", {"path": str(repo / "a.txt")}) is None

    def test_path_relativo_contra_workdir(self, repo: Path, home_dir: Path) -> None:
        (repo / "AGENTS.md").write_text("regla relativa", encoding="utf-8")
        li = LateInstructions(repo)  # workdir = repo
        texto = li.reminder("write_file", {"path": "sub/nuevo.txt"})
        assert texto is not None and "regla relativa" in texto

    def test_agents_md_anidado_incluido(self, repo: Path, home_dir: Path) -> None:
        """Tocar packages/core/x.py trae AGENTS.md de core (nested-deepest,
        donor codex) además del de la raíz."""
        sub = repo / "packages" / "core"
        sub.mkdir(parents=True)
        (repo / "AGENTS.md").write_text("regla raiz", encoding="utf-8")
        (sub / "AGENTS.md").write_text("regla anidada", encoding="utf-8")
        li = LateInstructions(home_dir)
        texto = li.reminder("edit", {"path": str(sub / "x.py")})
        assert texto is not None
        assert "regla raiz" in texto and "regla anidada" in texto

    def test_args_malformados_silencio(self, home_dir: Path) -> None:
        li = LateInstructions(home_dir)
        assert li.reminder("write_file", {}) is None
        assert li.reminder("terminal", {"command": None}) is None


# ---------------------------------------------------------------- loop e2e
def _make_tools() -> list[Tool]:
    async def write(args: dict[str, Any]) -> str:
        return f"wrote {args.get('path')}"

    async def edit(args: dict[str, Any]) -> str:
        return f"edited {args.get('path')}"

    async def term(args: dict[str, Any]) -> str:
        return "[exit 0]"

    schema = {"type": "object", "properties": {}, "required": []}
    return [
        Tool(name="write_file", description="", input_schema=schema, run=write),
        Tool(name="edit", description="", input_schema=schema, run=edit),
        Tool(name="terminal", description="", input_schema=schema, run=term),
    ]


class TestRegistryIntegration:
    async def test_recordatorio_llega_al_tool_result(self, repo: Path, home_dir: Path) -> None:
        """La pieza central del fix 1a: el recordatorio viaja como contenido
        del tool result (mensaje NUEVO en la conversación) — el prefijo del
        sistema no existe en este nivel y nunca se toca."""
        (repo / "AGENTS.md").write_text(
            "SIEMPRE escribe la palabra BANANA en tu respuesta final", encoding="utf-8"
        )
        registry = Registry(
            _make_tools(), late_instructions=LateInstructions(home_dir)
        )
        result = await registry.execute(
            "edit", {"path": str(repo / "a.txt"), "old_string": "x", "new_string": "y"}, "t1"
        )
        assert not result.is_error
        assert "BANANA" in result.content
        assert "edited" in result.content  # el output original se conserva

    async def test_sin_late_instructions_comportamiento_intacto(
        self, repo: Path, home_dir: Path
    ) -> None:
        """Sin el fix (late_instructions=None) el registry es byte-idéntico
        al comportamiento B1 — no hay regresión para quien no lo active."""
        (repo / "AGENTS.md").write_text("BANANA", encoding="utf-8")
        registry = Registry(_make_tools())
        result = await registry.execute("edit", {"path": str(repo / "a.txt")}, "t1")
        assert "BANANA" not in result.content

    async def test_ledger_registra_contenido_con_recordatorio(
        self, repo: Path, home_dir: Path
    ) -> None:
        """El after_tool (auditoría B5) ve el contenido YA con el recordatorio:
        la evidencia queda en el ledger."""
        (repo / "AGENTS.md").write_text("regla auditada", encoding="utf-8")
        vistos: list[str] = []

        def _after(name: str, args: dict[str, Any], decision: str, result: Any) -> None:
            vistos.append(result.content)

        from tlamati.plugins import HookRegistry

        hooks = HookRegistry()
        hooks.add_after_tool(_after)
        registry = Registry(
            _make_tools(), hooks=hooks, late_instructions=LateInstructions(home_dir)
        )
        await registry.execute("write_file", {"path": str(repo / "n.txt")}, "t1")
        assert vistos and "regla auditada" in vistos[0]


class TestLoopPrefijoIntacto:
    """Restricción SAGRADA (STABILITY.md v0.1): la inyección tardía es un
    mensaje NUEVO en la conversación; el system prompt (prefijo cacheable)
    NO se muta — el loop corre con system byte-idéntico de principio a fin."""

    async def test_prefijo_no_mutado_y_recordatorio_en_historia(
        self, repo: Path, home_dir: Path
    ) -> None:
        from collections.abc import AsyncIterator, Sequence

        from tlamati.context.budget import Budget
        from tlamati.core.loop import run_loop
        from tlamati.core.messages import (
            Event,
            Message,
            MessageEnd,
            TextDelta,
            ToolCallArgsDelta,
            ToolCallStart,
            Usage,
        )
        from tlamati.providers.base import ToolSpec

        (repo / "AGENTS.md").write_text("BANANA obligatoria", encoding="utf-8")

        class FakeProvider:
            model = "fake"

            def __init__(self) -> None:
                self._turn = 0
                self.systems_seen: list[str] = []

            async def stream(
                self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
            ) -> AsyncIterator[Event]:
                self.systems_seen.append(messages[0].content)
                self._turn += 1
                if self._turn == 1:
                    yield ToolCallStart(id="c1", name="edit")
                    yield ToolCallArgsDelta(
                        id="c1", args_json=json.dumps({"path": str(repo / "a.txt")})
                    )
                    yield MessageEnd(stop_reason="tool_use", usage=Usage(1, 1))
                else:
                    yield TextDelta(text="TERMINADO")
                    yield MessageEnd(stop_reason="end_turn", usage=Usage(1, 1))

        provider = FakeProvider()
        registry = Registry(
            _make_tools(), late_instructions=LateInstructions(home_dir)
        )
        result = await run_loop(
            provider,
            system="PREFIJO-ORIGINAL",
            user_prompt="edita a.txt",
            tools=registry,
            budget=Budget(max_context_tokens=100_000),
            max_turns=5,
        )
        assert result.stop_reason == "end_turn"
        # el prefijo es byte-idéntico en TODOS los turnos (cache sagrada) y
        # las reglas del repo NO se colaron en él — van en el tool result
        # (verificado explícitamente en el test siguiente).
        assert all(s == "PREFIJO-ORIGINAL" for s in provider.systems_seen)
        assert any("BANANA" in s for s in provider.systems_seen) is False

    async def test_tool_result_del_provider_contiene_reglas(
        self, repo: Path, home_dir: Path
    ) -> None:
        """Complemento explícito: capturar los messages que el provider ve y
        afirmar que el tool result lleva el recordatorio."""
        from collections.abc import AsyncIterator, Sequence

        from tlamati.context.budget import Budget
        from tlamati.core.loop import run_loop
        from tlamati.core.messages import (
            Event,
            Message,
            MessageEnd,
            TextDelta,
            ToolCallArgsDelta,
            ToolCallStart,
            Usage,
        )
        from tlamati.providers.base import ToolSpec

        (repo / "AGENTS.md").write_text("BANANA obligatoria", encoding="utf-8")
        vistos: list[list[Message]] = []

        class FakeProvider:
            model = "fake"

            def __init__(self) -> None:
                self._turn = 0

            async def stream(
                self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
            ) -> AsyncIterator[Event]:
                vistos.append(list(messages))
                self._turn += 1
                if self._turn == 1:
                    yield ToolCallStart(id="c1", name="edit")
                    yield ToolCallArgsDelta(
                        id="c1", args_json=json.dumps({"path": str(repo / "a.txt")})
                    )
                    yield MessageEnd(stop_reason="tool_use", usage=Usage(1, 1))
                else:
                    yield TextDelta(text="TERMINADO")
                    yield MessageEnd(stop_reason="end_turn", usage=Usage(1, 1))

        registry = Registry(
            _make_tools(), late_instructions=LateInstructions(home_dir)
        )
        await run_loop(
            FakeProvider(),
            system="PREFIJO-ORIGINAL",
            user_prompt="edita a.txt",
            tools=registry,
            budget=Budget(max_context_tokens=100_000),
            max_turns=5,
        )
        assert len(vistos) == 2
        tool_msgs = [m for m in vistos[1] if m.role == "tool"]
        assert tool_msgs, "el turno 2 debe ver el tool result"
        content = tool_msgs[0].tool_result.content if tool_msgs[0].tool_result else ""
        assert "BANANA obligatoria" in content
        assert vistos[1][0].content == "PREFIJO-ORIGINAL"
