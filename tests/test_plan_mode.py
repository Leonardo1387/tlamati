"""Tests C5 — plan-mode (plan/mode.py + plan/tools.py + policy transversal).

Cubre el flujo de integración del handoff §6.3:
entrar → write denegado → exit sin aprobación fail-closed → exit aprobado →
write permitido; doble-salida; rechazo con feedback.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

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
from tlamati.plan.mode import PLAN_MODE_PROMPT, PLAN_READONLY_TOOLS, PLAN_TOOLS, PlanState
from tlamati.plan.tools import make_plan_tools, plans_dir
from tlamati.policy.config import Policy, PolicyConfig
from tlamati.providers.base import ToolSpec
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Permission, Registry


class FakeProvider:
    """Scripted provider (mismo patrón que test_loop.py) — cero red."""

    model = "fake"

    def __init__(self, turns: list[list[tuple[Any, ...]]]) -> None:
        self.turns = turns
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
            usage=Usage(input_tokens=10, output_tokens=5),
        )


def _approver(verdict: bool | str) -> tuple[Callable[[str, str], Awaitable[bool | str]], list[str]]:
    """Aprobador de pruebas que registra los paths que vio."""
    seen: list[str] = []

    async def approve(path: str, content: str) -> bool | str:
        seen.append(path)
        return verdict

    return approve, seen


def _registry(cwd: Path, state: PlanState, approver: Any = None) -> Registry:
    tools = make_tools(cwd)
    tools.extend(make_plan_tools(cwd, state, plan_approver=approver))
    return Registry(tools, policy=Policy(PolicyConfig(), plan_state=state))


class TestPlanState:
    def test_enter_exit_happy_path(self) -> None:
        s = PlanState()
        assert s.enter() is None
        assert s.active and s.revision == 1
        rev = s.request_exit()
        assert rev == 1
        assert s.commit_exit(rev) == "normal"
        assert not s.active

    def test_enter_twice_fails_honest(self) -> None:
        s = PlanState()
        s.enter()
        err = s.enter()
        assert err is not None and err.startswith("ERROR")
        assert s.active  # sigue activo, fail cerrado

    def test_double_request_same_revision_fails_closed(self) -> None:
        """Regla de oro 2 (qwen): doble salida contra la misma revisión."""
        s = PlanState()
        s.enter()
        assert s.request_exit() == 1
        assert s.request_exit() is None  # segunda petición → rancia

    async def test_stale_revision_commit_fails_closed(self) -> None:
        """Regla 3: aprobación con revisión que no coincide → no conmuta."""
        s = PlanState()
        s.enter()
        assert s.commit_exit(999) is None
        assert s.active
        rev = s.request_exit()
        assert rev is not None
        assert s.commit_exit(rev + 100) is None
        assert s.active

    def test_commit_without_active_fails(self) -> None:
        s = PlanState()
        assert s.commit_exit(0) is None
        assert s.request_exit() is None

    def test_reject_then_retry(self) -> None:
        """Tras rechazo (cancel_exit) el modelo puede volver a pedir salida."""
        s = PlanState()
        s.enter()
        rev = s.request_exit()
        s.cancel_exit()  # rechazo
        rev2 = s.request_exit()
        assert rev2 == rev  # misma revisión, señal liberada
        assert s.commit_exit(rev2) == "normal"

    def test_started_active(self) -> None:
        s = PlanState(active=True)
        assert s.active
        err = s.enter()  # ya activo → error honesto
        assert err is not None


class TestPolicyLayer:
    def test_readonly_whitelist_allowed(self) -> None:
        s = PlanState(active=True)
        p = Policy(plan_state=s)
        for name in PLAN_READONLY_TOOLS:
            assert p.resolve(name, {}, Permission.AUTO) is Permission.AUTO
        for name in PLAN_TOOLS:
            assert p.resolve(name, {}, Permission.AUTO) is Permission.AUTO

    def test_write_tools_denied_in_plan_mode(self) -> None:
        s = PlanState(active=True)
        p = Policy(plan_state=s)
        for name in ("write_file", "edit", "terminal", "memory"):
            assert p.resolve(name, {}, Permission.AUTO) is Permission.DENY

    def test_inactive_plan_mode_no_effect(self) -> None:
        p = Policy(plan_state=PlanState(active=False))
        assert p.resolve("write_file", {}, Permission.AUTO) is Permission.AUTO

    def test_no_plan_state_no_effect(self) -> None:
        """B4 intacto: Policy sin plan_state se comporta igual que antes."""
        p = Policy()
        assert p.resolve("write_file", {}, Permission.AUTO) is Permission.AUTO
        assert p.plan_denied("write_file") is False


class TestPlanTools:
    async def test_save_plan_writes_inside_plans_dir(self, tmp_path: Path) -> None:
        state = PlanState()
        tools = make_plan_tools(tmp_path, state)
        save = {t.name: t for t in tools}["save_plan"]
        out = await save.run({"name": "mi-plan", "content": "# Paso 1\nhacer X"})
        assert not out.startswith("ERROR")
        target = plans_dir(tmp_path) / "mi-plan.md"
        assert target.is_file()
        assert "hacer X" in target.read_text()

    async def test_save_plan_rejects_bad_name(self, tmp_path: Path) -> None:
        state = PlanState()
        save = {t.name: t for t in make_plan_tools(tmp_path, state)}["save_plan"]
        out = await save.run({"name": "../../escape", "content": "x"})
        assert out.startswith("ERROR")
        assert not (tmp_path / "escape.md").exists()

    async def test_save_plan_rejects_empty(self, tmp_path: Path) -> None:
        save = {t.name: t for t in make_plan_tools(tmp_path, PlanState())}["save_plan"]
        out = await save.run({"name": "p", "content": "   "})
        assert out.startswith("ERROR")

    async def test_exit_requires_plan_mode(self, tmp_path: Path) -> None:
        exit_t = {t.name: t for t in make_plan_tools(tmp_path, PlanState())}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": "x.md"})
        assert "no estás en plan-mode" in out

    async def test_exit_path_escape_guard(self, tmp_path: Path) -> None:
        state = PlanState(active=True)
        exit_t = {t.name: t for t in make_plan_tools(tmp_path, state)}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": str(tmp_path / "fuera.md")})
        assert out.startswith("ERROR") and "fuera de .tlamati/plans/" in out
        assert state.active  # fail closed

    async def test_exit_missing_file(self, tmp_path: Path) -> None:
        state = PlanState(active=True)
        pdir = plans_dir(tmp_path)
        pdir.mkdir(parents=True)
        exit_t = {t.name: t for t in make_plan_tools(tmp_path, state)}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": str(pdir / "no-existe.md")})
        assert "no existe" in out
        assert state.active

    async def test_exit_headless_no_approver_fails_closed(self, tmp_path: Path) -> None:
        """Regla de oro 1 (qwen): sin host interactivo → fail closed."""
        state = PlanState(active=True)
        pdir = plans_dir(tmp_path)
        pdir.mkdir(parents=True)
        (pdir / "p.md").write_text("# plan")
        exit_t = {t.name: t for t in make_plan_tools(tmp_path, state)}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": str(pdir / "p.md")})
        assert "no hay un usuario interactivo" in out
        assert state.active

    async def test_exit_approved_exits(self, tmp_path: Path) -> None:
        state = PlanState(active=True)
        pdir = plans_dir(tmp_path)
        pdir.mkdir(parents=True)
        plan = pdir / "p.md"
        plan.write_text("# plan")
        approve, seen = _approver(True)
        exit_t = {t.name: t for t in make_plan_tools(tmp_path, state, approve)}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": str(plan)})
        assert "APROBADO" in out
        assert not state.active
        assert seen == [str(plan)]

    async def test_exit_rejected_with_feedback_stays(self, tmp_path: Path) -> None:
        """Regla gemini 6: rechazo = feedback, sigue en plan-mode."""
        state = PlanState(active=True)
        pdir = plans_dir(tmp_path)
        pdir.mkdir(parents=True)
        plan = pdir / "p.md"
        plan.write_text("# plan")
        approve, _ = _approver("faltan los tests")
        exit_t = {t.name: t for t in make_plan_tools(tmp_path, state, approve)}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": str(plan)})
        assert "RECHAZADO" in out and "faltan los tests" in out
        assert state.active
        # Tras rechazo puede volver a pedir salida (señal liberada).
        approve2, _ = _approver(True)
        tools2 = make_plan_tools(tmp_path, state, approve2)
        exit2 = {t.name: t for t in tools2}["exit_plan_mode"]
        out2 = await exit2.run({"plan_path": str(plan)})
        assert "APROBADO" in out2

    async def test_double_exit_same_revision_fails_closed(self, tmp_path: Path) -> None:
        """Regla de oro 2: doble petición contra la misma revisión."""
        state = PlanState(active=True)
        pdir = plans_dir(tmp_path)
        pdir.mkdir(parents=True)
        plan = pdir / "p.md"
        plan.write_text("# plan")

        async def slow_approve(path: str, content: str) -> bool:
            # Simula la primera petición aún "en vuelo": no devuelve True.
            return False

        plan_tools = make_plan_tools(tmp_path, state, slow_approve)
        exit_t = {t.name: t for t in plan_tools}["exit_plan_mode"]
        out1 = await exit_t.run({"plan_path": str(plan)})
        assert "RECHAZADO" in out1  # libera la señal tras el rechazo

        # Ahora una doble salida real: la primera consume la señal.
        rev = state.request_exit()
        assert rev is not None
        out = await exit_t.run({"plan_path": str(plan)})
        assert "en vuelo" in out and "SIGUE ACTIVO" in out
        assert state.active

    async def test_approver_exception_fails_closed(self, tmp_path: Path) -> None:
        state = PlanState(active=True)
        pdir = plans_dir(tmp_path)
        pdir.mkdir(parents=True)
        (pdir / "p.md").write_text("# plan")

        async def boom(path: str, content: str) -> bool:
            raise RuntimeError("approver roto")

        exit_t = {t.name: t for t in make_plan_tools(tmp_path, state, boom)}["exit_plan_mode"]
        out = await exit_t.run({"plan_path": str(pdir / "p.md")})
        assert "Fail closed" in out
        assert state.active


class TestIntegrationLoop:
    """El flujo completo del handoff §6.3 con FakeProvider — cero red."""

    async def test_full_flow_enter_deny_exit_approve_write(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n")
        state = PlanState()
        approve, _ = _approver(True)
        reg = _registry(tmp_path, state, approve)
        provider = FakeProvider(
            [
                # Turno 1: entrar en plan-mode.
                [("tool", "t1", "enter_plan_mode", {"reason": "tarea no trivial"})],
                # Turno 2: intentar escribir → DENEGADO por plan-mode.
                [("tool", "t2", "write_file", {"path": "app.py", "content": "x = 2\n"})],
                # Turno 3: guardar el plan.
                [
                    (
                        "tool",
                        "t3",
                        "save_plan",
                        {"name": "fix", "content": "# Plan\ncambiar x a 2"},
                    )
                ],
                # Turno 4: pedir salida (aprobador dice True).
                [
                    (
                        "tool",
                        "t4",
                        "exit_plan_mode",
                        {"plan_path": str(plans_dir(tmp_path) / "fix.md")},
                    )
                ],
                # Turno 5: escribir ya aprobado → permitido.
                [("tool", "t5", "write_file", {"path": "app.py", "content": "x = 2\n"})],
                # Turno 6: fin.
                [("text", "TERMINADO")],
            ]
        )
        result = await run_loop(
            provider,
            system="s" + PLAN_MODE_PROMPT,
            user_prompt="arregla app.py",
            tools=reg,
            budget=Budget(100_000),
            max_turns=10,
        )
        assert result.stop_reason == "end_turn"
        # El write del turno 2 fue denegado con el mensaje de plan-mode.
        tool_msgs = [m for m in provider.calls[-1] if m.role == "tool"]
        denied = [
            m for m in tool_msgs if m.tool_result and "PLAN-MODE" in (m.tool_result.content or "")
        ]
        assert len(denied) == 1
        # Y el archivo final tiene el contenido del turno 5 (permitido tras aprobar).
        assert (tmp_path / "app.py").read_text() == "x = 2\n"
        assert not state.active

    async def test_prefix_static_plan_prompt_always_present(self) -> None:
        """Decisión #3: el bloque de plan-mode es estático — mismos bytes con
        el modo activo o inactivo (cache sagrada)."""
        assert PLAN_MODE_PROMPT.startswith("\n\n# PLAN-MODE")
        # El prompt no menciona estado dinámico (activo/inactivo de corrida).
        assert "ACTIVO" not in PLAN_MODE_PROMPT


class TestCliFlags:
    def test_plan_mode_flag_parsed(self) -> None:
        from tlamati.cli import build_parser

        args = build_parser().parse_args(["-p", "x", "--plan-mode"])
        assert args.plan_mode is True

    def test_plan_mode_yolo_mutually_exclusive(self, capsys: Any) -> None:
        """Regla gemini 7: fail fast al parsear."""
        import asyncio

        from tlamati.cli import _run_headless, build_parser

        args = build_parser().parse_args(["-p", "x", "--plan-mode", "--approve-tool", "*"])
        rc = asyncio.run(_run_headless(args))
        assert rc == 2
        assert "mutuamente exclusivos" in capsys.readouterr().err


class TestRegistryHonestError:
    async def test_deny_message_mentions_plan_mode(self, tmp_path: Path) -> None:
        state = PlanState(active=True)
        reg = _registry(tmp_path, state)
        res = await reg.execute("write_file", {"path": "x", "content": "y"}, "c1")
        assert res.is_error
        assert "PLAN-MODE" in res.content
        assert "exit_plan_mode" in res.content

    async def test_b4_deny_message_unchanged(self, tmp_path: Path) -> None:
        """Sin plan-mode, el mensaje de DENY de B4 sigue intacto."""
        reg = Registry(
            make_tools(tmp_path),
            policy=Policy(PolicyConfig(tool_overrides={"write_file": Permission.DENY})),
        )
        res = await reg.execute("write_file", {"path": "x", "content": "y"}, "c1")
        assert res.is_error
        assert "denied by policy" in res.content
        assert "PLAN-MODE" not in res.content
