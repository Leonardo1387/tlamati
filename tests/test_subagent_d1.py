"""D1 — tests de subagent/spawn.py: delegación con límites.

Unidades: toolset read-only del hijo, profundidad 1 fail fast, tope de gasto
heredado, resumen-no-transcript, auditoría con prefijo de sesión hija.
Integración: padre FakeProvider delega → hijo corre → padre recibe solo
final_text. Cero red, cero costo.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

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
from tlamati.policy.ledger import Ledger
from tlamati.providers.base import ToolSpec
from tlamati.subagent.spawn import (
    DELEGATE_TOOL_NAME,
    SubagentConfig,
    build_child_tools,
    make_delegate_tool,
)
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Permission, Registry, Tool


class FakeProvider:
    """Scripted provider (mismo patrón que test_loop.py)."""

    model = "fake"

    def __init__(self, turns: list[list[tuple[Any, ...]]], usage: Usage | None = None) -> None:
        self.turns = turns
        self.usage = usage or Usage(input_tokens=10, output_tokens=5)
        self.calls: list[list[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.calls.append(list(messages))
        script = self.turns.pop(0) if self.turns else [("text", "fin")]
        has_tools = False
        for step in script:
            if step[0] == "text":
                yield TextDelta(text=str(step[1]))
            elif step[0] == "tool":
                tid, name, args = str(step[1]), str(step[2]), step[3]
                yield ToolCallStart(id=tid, name=name)
                yield ToolCallArgsDelta(id=tid, args_json=json.dumps(args))
                has_tools = True
        yield MessageEnd(
            stop_reason="tool_use" if has_tools else "end_turn",
            usage=self.usage,
        )


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "nota.txt").write_text("contenido secreto del proyecto\n")
    return tmp_path


def _delegate(
    provider: Any, workdir: Path, *, cfg: SubagentConfig | None = None, ledger: Ledger | None = None
) -> Tool:
    return make_delegate_tool(
        provider,
        tool_candidates=lambda: make_tools(workdir, sandbox=False),
        config=cfg or SubagentConfig(),
        ledger=ledger,
    )


# ---------------------------------------------------------------- unidades


class TestBuildChildTools:
    def test_solo_readonly_whitelist(self, workdir: Path) -> None:
        child = build_child_tools(make_tools(workdir, sandbox=False))
        names = {t.name for t in child}
        assert names == {"read_file", "search_files"}
        assert "write_file" not in names
        assert "edit" not in names
        assert "terminal" not in names

    def test_delegate_en_candidatos_es_fail_fast(self, workdir: Path) -> None:
        candidates = make_tools(workdir, sandbox=False)
        candidates.append(
            Tool(
                name=DELEGATE_TOOL_NAME,
                description="x",
                input_schema={},
                run=lambda a: None,  # type: ignore[arg-type, return-value]
            )
        )
        with pytest.raises(ValueError, match="profundidad máxima 1"):
            build_child_tools(candidates)

    def test_escalera_solo_endurece_sin_auto(self, workdir: Path) -> None:
        ask_tool = Tool(
            name="read_file",  # read-only pero con ASK → el hijo la descarta
            description="x",
            input_schema={},
            run=lambda a: None,  # type: ignore[arg-type, return-value]
            permission=Permission.ASK,
        )
        assert build_child_tools([ask_tool]) == []


class TestSubagentConfig:
    def test_hereda_tope_del_padre_nunca_lo_supera(self) -> None:
        cfg = SubagentConfig.from_dict({"max_context_tokens": 500_000}, parent_context=64_000)
        assert cfg.max_context_tokens == 64_000

    def test_defaults_con_padre_grande(self) -> None:
        cfg = SubagentConfig.from_dict(None, parent_context=128_000)
        assert cfg.max_context_tokens == 128_000
        assert cfg.max_turns_cap == 25


# ---------------------------------------------------------------- integración


class TestDelegateTool:
    async def test_hijo_corre_y_padre_recibe_solo_resumen(self, workdir: Path) -> None:
        child_p = FakeProvider(
            [
                [("tool", "s1", "read_file", {"path": "nota.txt"})],
                [("text", "RESUMEN DEL HIJO: el archivo dice contenido secreto")],
            ]
        )
        tool = _delegate(child_p, workdir)
        out = await tool.run({"goal": "lee nota.txt y resume"})
        assert "RESUMEN DEL HIJO" in out
        assert "stop=end_turn" in out
        # El hijo vio la tarea y el tool read_file; nunca write/terminal.
        specs_sent = child_p.calls[0]
        assert specs_sent[0].role == "system"
        assert "SUBAGENTE" in specs_sent[0].content
        assert "# TAREA" in specs_sent[1].content

    async def test_no_filtra_transcript_del_hijo(self, workdir: Path) -> None:
        # El hijo produce texto intermedio largo; el padre solo ve el FINAL.
        child_p = FakeProvider(
            [
                [("tool", "s1", "read_file", {"path": "nota.txt"})],
                [
                    ("text", "PENSAMIENTO INTERNO QUE NO DEBE VIAJAR " * 50),
                    ("tool", "s2", "search_files", {"pattern": "secreto"}),
                ],
                [("text", "RESUMEN CORTO")],
            ]
        )
        tool = _delegate(child_p, workdir)
        out = await tool.run({"goal": "explora"})
        assert "RESUMEN CORTO" in out
        assert "PENSAMIENTO INTERNO" not in out

    async def test_goal_vacio_error_honesto(self, workdir: Path) -> None:
        tool = _delegate(FakeProvider([]), workdir)
        out = await tool.run({"goal": "  "})
        assert out.startswith("ERROR:")

    async def test_tope_de_gasto_retorna_honesto(self, workdir: Path) -> None:
        # usage 10+5=15 por turno; tope 15 → tras el 1er turno el 2do NO gasta.
        child_p = FakeProvider(
            [
                [("tool", "s1", "read_file", {"path": "nota.txt"})],
                [("text", "no deberé correr")],
                [("text", "tampoco")],
            ]
        )
        cfg = SubagentConfig(max_total_tokens=15)
        tool = _delegate(child_p, workdir, cfg=cfg)
        out = await tool.run({"goal": "explora"})
        assert "TOPE DE GASTO" in out
        assert len(child_p.calls) == 1  # el 2do turno se bloqueó ANTES de gastar

    async def test_max_turns_cap_se_respeta(self, workdir: Path) -> None:
        # offset variable: progreso real → mide el CAP, no el detector E3d.
        child_p = FakeProvider(
            [
                [("tool", f"s{i}", "read_file", {"path": "nota.txt", "offset": i + 1})]
                for i in range(50)
            ]
        )
        cfg = SubagentConfig(max_turns_cap=3, max_turns_default=2)
        tool = _delegate(child_p, workdir, cfg=cfg)
        out = await tool.run({"goal": "explora", "max_turns": 999})
        assert "stop=max_turns" in out
        assert "LÍMITE DE TURNOS" in out
        assert len(child_p.calls) == 3

    async def test_nieto_es_error_honesto_no_excepcion(self, workdir: Path) -> None:
        # Si somehow delegate_task entra a los candidatos → ERROR, no crash.
        delegate_itself = _delegate(FakeProvider([]), workdir)
        tool = make_delegate_tool(
            FakeProvider([]),
            tool_candidates=lambda: [*make_tools(workdir, sandbox=False), delegate_itself],
            config=SubagentConfig(),
        )
        out = await tool.run({"goal": "x"})
        assert out.startswith("ERROR:")
        assert "profundidad máxima 1" in out

    async def test_permiso_default_ask(self, workdir: Path) -> None:
        assert _delegate(FakeProvider([]), workdir).permission is Permission.ASK

    async def test_no_registrado_en_hijo(self, workdir: Path) -> None:
        # El Registry del hijo se construye con build_child_tools: nunca tiene
        # delegate_task aunque el padre lo tenga registrado.
        child_p = FakeProvider(
            [[("tool", "s1", DELEGATE_TOOL_NAME, {"goal": "nieto"})], [("text", "FIN HIJO")]]
        )
        tool = _delegate(child_p, workdir)
        out = await tool.run({"goal": "explora"})
        # La llamada del hijo a delegate_task → unknown tool (error honesto).
        assert "FIN HIJO" in out


class TestAuditoriaHija:
    async def test_eventos_del_hijo_al_mismo_ledger_con_prefijo(
        self, workdir: Path, tmp_path: Path
    ) -> None:
        db = tmp_path / "audit.db"
        parent_ledger = Ledger(db, "20261117-120000-abcdef12")
        child_p = FakeProvider(
            [
                [("tool", "s1", "read_file", {"path": "nota.txt"})],
                [("text", "RESUMEN")],
            ]
        )
        tool = _delegate(child_p, workdir, ledger=parent_ledger)
        out = await tool.run({"goal": "explora"})
        assert "sesión=20261117-120000-abcdef12:sub-01" in out

        sessions = {s[0] for s in Ledger.list_sessions(db)}
        assert "20261117-120000-abcdef12:sub-01" in sessions
        events, costs = Ledger.read_session(db, "20261117-120000-abcdef12:sub-01")
        assert any(e.tool == "read_file" and e.decision == "auto" for e in events)
        assert costs  # turn_costs del hijo registrados
        parent_ledger.close()

    async def test_segundo_spawn_incrementa_prefijo(self, workdir: Path, tmp_path: Path) -> None:
        db = tmp_path / "audit2.db"
        parent_ledger = Ledger(db, "20261117-130000-aaaaaaaa")
        child_p = FakeProvider([[("text", "ok1")], [("text", "ok2")]])
        tool = _delegate(child_p, workdir, ledger=parent_ledger)
        await tool.run({"goal": "uno"})
        out2 = await tool.run({"goal": "dos"})
        assert "sesión=20261117-130000-aaaaaaaa:sub-02" in out2
        parent_ledger.close()


class TestPadreCompleto:
    async def test_padre_delega_hijo_corre_padre_recibe_resumen(self, workdir: Path) -> None:
        """Integración FakeProvider completa: run_loop del padre con la tool
        registrada y approver que aprueba (ASK) → el resultado del tool entra
        al historial del padre con SOLO el resumen."""
        child_p = FakeProvider(
            [
                [("tool", "s1", "read_file", {"path": "nota.txt"})],
                [("text", "HIJO: archivo leído, dice contenido secreto")],
            ]
        )
        delegate = _delegate(child_p, workdir)
        parent_p = FakeProvider(
            [
                [("tool", "p1", DELEGATE_TOOL_NAME, {"goal": "lee nota.txt"})],
                [("text", "PADRE: terminé con el resumen del hijo")],
            ]
        )

        async def approver(name: str, args: dict[str, Any]) -> bool:
            return name == DELEGATE_TOOL_NAME

        registry = Registry([*make_tools(workdir, sandbox=False), delegate], approver=approver)
        result = await run_loop(
            parent_p,
            system="s",
            user_prompt="delega la lectura",
            tools=registry,
            budget=Budget(100_000),
        )
        assert result.stop_reason == "end_turn"
        # El tool result del padre contiene el resumen, NO el transcript.
        tool_msgs = [m for m in parent_p.calls[1] if m.role == "tool"]
        assert len(tool_msgs) == 1
        content = tool_msgs[0].tool_result.content if tool_msgs[0].tool_result else ""
        assert content is not None
        assert "HIJO: archivo leído" in content
        assert "PENSAMIENTO" not in content
