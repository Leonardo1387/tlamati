"""B4 — policy: overrides, patrones de comando, trifecta untrusted→ask.

La escalera NUNCA relaja: deny > ask > auto en cada capa.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from tlamati.policy.config import Policy, PolicyConfig
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Permission, Registry, Tool


def _echo_tool(
    name: str = "echo", permission: Permission = Permission.AUTO, untrusted: bool = False
) -> Tool:
    async def run(args: dict[str, Any]) -> str:
        return f"ran {name}"

    return Tool(
        name=name,
        description="test",
        input_schema={"type": "object", "properties": {}, "required": []},
        run=run,
        permission=permission,
        produces_untrusted=untrusted,
    )


class TestPolicyConfigParsing:
    def test_empty_config_defaults(self) -> None:
        cfg = PolicyConfig.from_dict(None)
        assert cfg.tool_overrides == {} and cfg.deny_commands == ()
        assert "terminal" in cfg.egress_tools

    def test_valid_yaml_shape(self) -> None:
        cfg = PolicyConfig.from_dict(
            {
                "tools": {"write_file": "ask", "terminal": "deny"},
                "deny_commands": ["rm -rf *"],
                "ask_commands": ["git push*"],
            }
        )
        assert cfg.tool_overrides["write_file"] is Permission.ASK
        assert cfg.tool_overrides["terminal"] is Permission.DENY
        assert cfg.deny_commands == ("rm -rf *",)

    def test_invalid_level_fail_fast(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            PolicyConfig.from_dict({"tools": {"terminal": "yolo"}})

    def test_invalid_shape_fail_fast(self) -> None:
        with pytest.raises(ValueError, match="debe ser un mapa"):
            PolicyConfig.from_dict("no-es-mapa")  # type: ignore[arg-type]


class TestResolutionLadder:
    def test_override_hardens(self) -> None:
        p = Policy(PolicyConfig(tool_overrides={"echo": Permission.DENY}))
        assert p.resolve("echo", {}, Permission.AUTO) is Permission.DENY

    def test_override_relaxes(self) -> None:
        p = Policy(PolicyConfig(tool_overrides={"echo": Permission.AUTO}))
        assert p.resolve("echo", {}, Permission.ASK) is Permission.AUTO

    def test_deny_command_beats_auto(self) -> None:
        p = Policy(PolicyConfig(deny_commands=("rm -rf *",)))
        assert p.resolve("terminal", {"command": "rm -rf /"}, Permission.AUTO) is Permission.DENY

    def test_ask_command_hardens(self) -> None:
        p = Policy(PolicyConfig(ask_commands=("git push*",)))
        got = p.resolve("terminal", {"command": "git push origin"}, Permission.AUTO)
        assert got is Permission.ASK

    def test_ask_command_never_relaxes_deny(self) -> None:
        p = Policy(PolicyConfig(ask_commands=("*",)))
        assert p.resolve("terminal", {"command": "x"}, Permission.DENY) is Permission.DENY

    def test_non_command_args_ignore_patterns(self) -> None:
        p = Policy(PolicyConfig(deny_commands=("*",)))
        assert p.resolve("read_file", {"path": "a.txt"}, Permission.AUTO) is Permission.AUTO


class TestTrifecta:
    def test_egress_auto_escalates_after_untrusted(self) -> None:
        p = Policy()
        assert p.resolve("terminal", {"command": "curl x"}, Permission.AUTO) is Permission.AUTO
        p.mark_untrusted()
        assert p.resolve("terminal", {"command": "curl x"}, Permission.AUTO) is Permission.ASK

    def test_non_egress_unaffected(self) -> None:
        p = Policy()
        p.mark_untrusted()
        assert p.resolve("read_file", {}, Permission.AUTO) is Permission.AUTO

    def test_trifecta_never_relaxes_deny(self) -> None:
        p = Policy()
        p.mark_untrusted()
        assert p.resolve("terminal", {}, Permission.DENY) is Permission.DENY

    def test_custom_egress_set(self) -> None:
        p = Policy(PolicyConfig(egress_tools=frozenset({"web_fetch"})))
        p.mark_untrusted()
        assert p.resolve("terminal", {}, Permission.AUTO) is Permission.AUTO
        assert p.resolve("web_fetch", {}, Permission.AUTO) is Permission.ASK


class TestRegistryIntegration:
    async def test_denied_by_pattern_never_runs(self) -> None:
        reg = Registry(
            [
                Tool(
                    name="terminal",
                    description="d",
                    input_schema={
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                    run=lambda a: asyncio.sleep(0, result="NO DEBE CORRER"),
                )
            ],
            policy=Policy(PolicyConfig(deny_commands=("rm -rf *",))),
        )
        res = await reg.execute("terminal", {"command": "rm -rf /"}, "c1")
        assert res.is_error and "denied by policy" in res.content

    async def test_untrusted_result_marks_policy_and_flags_result(self, tmp_path: Path) -> None:
        reg = Registry([_echo_tool("fetch", untrusted=True)], policy=Policy())
        res = await reg.execute("fetch", {}, "c1")
        assert res.untrusted is True
        assert reg.policy is not None and reg.policy.untrusted_seen

    async def test_error_result_not_untrusted(self) -> None:
        async def boom(args: dict[str, Any]) -> str:
            return "ERROR: fetch falló"

        t = Tool(
            name="fetch",
            description="d",
            input_schema={"type": "object", "properties": {}, "required": []},
            run=boom,
            produces_untrusted=True,
        )
        reg = Registry([t], policy=Policy())
        res = await reg.execute("fetch", {}, "c1")
        assert res.is_error and res.untrusted is False
        assert reg.policy is not None and not reg.policy.untrusted_seen

    async def test_escalated_ask_without_approver_honest(self) -> None:
        reg = Registry(
            [_echo_tool("fetch", untrusted=True), _echo_tool("terminal")], policy=Policy()
        )
        await reg.execute("fetch", {}, "c1")  # marca untrusted
        res = await reg.execute("terminal", {}, "c2")
        assert res.is_error and "escalated to approval" in res.content

    async def test_escalated_ask_with_approver_runs(self) -> None:
        approved: list[str] = []

        async def yes(name: str, args: dict[str, Any]) -> bool:
            approved.append(name)
            return True

        reg = Registry(
            [_echo_tool("fetch", untrusted=True), _echo_tool("terminal")],
            approver=yes,
            policy=Policy(),
        )
        await reg.execute("fetch", {}, "c1")
        res = await reg.execute("terminal", {}, "c2")
        assert not res.is_error and approved == ["terminal"]

    async def test_terminal_with_net_produces_untrusted(self, tmp_path: Path) -> None:
        # sandbox=False (sin jaula) → el output PUDO venir de la red
        reg = Registry(make_tools(tmp_path, sandbox=False), policy=Policy())
        await reg.execute("terminal", {"command": "echo x"}, "c1")
        assert reg.policy is not None and reg.policy.untrusted_seen

    async def test_terminal_jailed_no_net_not_untrusted(self, tmp_path: Path) -> None:
        # jaula con red OFF → nada cruza la frontera
        reg = Registry(make_tools(tmp_path, sandbox=True), policy=Policy())
        res = await reg.execute("terminal", {"command": "echo x"}, "c1")
        assert reg.policy is not None and not reg.policy.untrusted_seen
        assert res.untrusted is False


class TestHeadlessApprover:
    def test_cli_flag_shape(self) -> None:
        from tlamati.cli import build_parser

        args = build_parser().parse_args(["-p", "x", "--approve-tool", "terminal"])
        assert args.approve_tool == ["terminal"]

    def test_default_never_yolo(self) -> None:
        from tlamati.cli import _headless_approver

        approver = _headless_approver([])
        assert asyncio.run(approver("terminal", {})) is False

    def test_wildcard_approves_all(self) -> None:
        from tlamati.cli import _headless_approver

        approver = _headless_approver(["*"])
        assert asyncio.run(approver("cualquiera", {})) is True

    def test_named_tool_only(self) -> None:
        from tlamati.cli import _headless_approver

        approver = _headless_approver(["terminal"])
        assert asyncio.run(approver("terminal", {})) is True
        assert asyncio.run(approver("write_file", {})) is False
