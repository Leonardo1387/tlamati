"""B5 — ledger SQLite append-only + integración registry + CLI audit."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from tlamati.policy.config import Policy, PolicyConfig
from tlamati.policy.ledger import Ledger
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Permission, Registry, Tool


def _echo(name: str = "echo", untrusted: bool = False) -> Tool:
    async def run(args: dict[str, Any]) -> str:
        return "hola"

    return Tool(
        name=name,
        description="t",
        input_schema={"type": "object", "properties": {}, "required": []},
        run=run,
        produces_untrusted=untrusted,
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "audit.db"


class TestLedgerCore:
    def test_record_and_read_back(self, db: Path) -> None:
        led = Ledger(db, "ses-1")
        led.record_tool_event(
            tool="terminal",
            args={"command": "echo x"},
            decision="auto",
            result_content="salida",
        )
        led.close()
        events, _costs = Ledger.read_session(db, "ses-1")
        assert len(events) == 1
        e = events[0]
        assert e.tool == "terminal" and e.decision == "auto" and e.turn == 0
        assert e.args_json == '{"command": "echo x"}'
        # hash = sha256 del contenido exacto
        assert e.result_sha256 == hashlib.sha256(b"salida").hexdigest()

    def test_sessions_isolated(self, db: Path) -> None:
        a = Ledger(db, "ses-a")
        b = Ledger(db, "ses-b")
        a.record_tool_event(tool="t", args={}, decision="auto", result_content="1")
        b.record_tool_event(tool="t", args={}, decision="auto", result_content="2")
        b.record_tool_event(tool="t", args={}, decision="auto", result_content="3")
        a.close()
        b.close()
        ea, _ = Ledger.read_session(db, "ses-a")
        eb, _ = Ledger.read_session(db, "ses-b")
        assert len(ea) == 1 and len(eb) == 2

    def test_list_sessions(self, db: Path) -> None:
        for sid in ("s1", "s2"):
            led = Ledger(db, sid)
            led.record_tool_event(tool="t", args={}, decision="auto", result_content="x")
            led.close()
        sessions = Ledger.list_sessions(db)
        assert {s[0] for s in sessions} == {"s1", "s2"}
        assert all(n == 1 for _, n, _ in sessions)

    def test_turn_cost_recorded(self, db: Path) -> None:
        led = Ledger(db, "s")
        led.record_turn_cost(turn=1, input_tokens=10, output_tokens=5, cache_read=3, cost_usd=0.01)
        led.close()
        _, costs = Ledger.read_session(db, "s")
        assert costs[0].input_tokens == 10 and costs[0].cost_usd == 0.01

    def test_broken_ledger_does_not_raise(self, tmp_path: Path) -> None:
        # archivo NO directorio → sqlite3 falla al crear
        bad = tmp_path / "archivo"
        bad.write_text("x")
        led = Ledger.__new__(Ledger)  # simula ledger con conexión rota
        led.db_path = bad / "x.db"
        led.session_id = "s"
        led.turn = 0
        led.broken = None
        import sqlite3

        led._conn = sqlite3.connect(":memory:")
        led._conn.close()  # conexión cerrada → writes fallan
        led.record_tool_event(tool="t", args={}, decision="auto", result_content="x")
        assert led.broken is not None and "ProgrammingError" in led.broken


class TestRegistryIntegration:
    async def test_decisions_logged(self, db: Path) -> None:
        led = Ledger(db, "s")
        reg = Registry(
            [_echo(), _echo("vetado")],
            policy=Policy(PolicyConfig(tool_overrides={"vetado": Permission.DENY})),
            ledger=led,
        )
        await reg.execute("echo", {}, "c1")
        await reg.execute("vetado", {}, "c2")
        await reg.execute("fantasma", {}, "c3")
        led.close()
        events, _ = Ledger.read_session(db, "s")
        assert [(e.tool, e.decision) for e in events] == [
            ("echo", "auto"),
            ("vetado", "deny"),
            ("fantasma", "unknown"),
        ]

    async def test_untrusted_flag_in_ledger(self, db: Path) -> None:
        led = Ledger(db, "s")
        reg = Registry([_echo("fetch", untrusted=True)], policy=Policy(), ledger=led)
        await reg.execute("fetch", {}, "c1")
        led.close()
        events, _ = Ledger.read_session(db, "s")
        assert events[0].untrusted is True

    async def test_escalation_logged(self, db: Path) -> None:
        led = Ledger(db, "s")
        reg = Registry(
            [_echo("fetch", untrusted=True), _echo("terminal")], policy=Policy(), ledger=led
        )
        await reg.execute("fetch", {}, "c1")
        await reg.execute("terminal", {}, "c2")  # trifecta → ask sin approver
        led.close()
        events, _ = Ledger.read_session(db, "s")
        assert events[1].decision == "ask_escalated" and events[1].is_error

    async def test_turn_number_travels(self, db: Path, tmp_path: Path) -> None:
        led = Ledger(db, "s")
        led.turn = 3
        reg = Registry(make_tools(tmp_path, sandbox=True), policy=Policy(), ledger=led)
        await reg.execute("terminal", {"command": "echo x"}, "c1")
        led.close()
        events, _ = Ledger.read_session(db, "s")
        assert events[0].turn == 3

    async def test_no_ledger_no_crash(self, tmp_path: Path) -> None:
        reg = Registry([_echo()], policy=Policy())
        res = await reg.execute("echo", {}, "c1")
        assert not res.is_error


class TestCliAudit:
    def test_audit_lists_and_shows(self, db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from tlamati.cli import _run_audit, build_parser

        led = Ledger(db, "ses-cli")
        led.record_tool_event(
            tool="terminal", args={"command": "ls"}, decision="auto", result_content="x"
        )
        led.close()

        parser = build_parser()
        args = parser.parse_args(["audit", "--audit-db", str(db)])
        assert _run_audit(args) == 0
        assert "ses-cli" in capsys.readouterr().out

        args = parser.parse_args(["audit", "--audit-db", str(db), "--session", "ses-cli"])
        assert _run_audit(args) == 0
        out = capsys.readouterr().out
        assert "terminal" in out and "auto" in out and "sha256=" in out

    def test_audit_missing_db_honest(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tlamati.cli import _run_audit, build_parser

        args = build_parser().parse_args(["audit", "--audit-db", str(tmp_path / "nope.db")])
        assert _run_audit(args) == 2
        assert "no existe" in capsys.readouterr().err

    def test_audit_unknown_session_honest(
        self, db: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tlamati.cli import _run_audit, build_parser

        Ledger(db, "x").close()
        args = build_parser().parse_args(["audit", "--audit-db", str(db), "--session", "ghost"])
        assert _run_audit(args) == 2
        assert "no encontrada" in capsys.readouterr().err

    def test_unknown_subcommand(self) -> None:
        from tlamati.cli import main

        assert main(["basura"]) == 2
