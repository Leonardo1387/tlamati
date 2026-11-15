"""B1 — registry tests: schema validation BEFORE execution, permission gate,
honest degradation, loop integration."""

from __future__ import annotations

from typing import Any

import pytest

from tlamati.tools.registry import Permission, Registry, Tool, truncate, validate_schema


async def _echo(args: dict[str, Any]) -> str:
    return f"echo:{args.get('msg', '')}"


async def _boom(args: dict[str, Any]) -> str:
    raise RuntimeError("kaboom")


def _tool(
    name: str = "echo",
    permission: Permission = Permission.AUTO,
    schema: dict[str, Any] | None = None,
    run: Any = _echo,
) -> Tool:
    return Tool(
        name=name,
        description="test tool",
        input_schema=schema
        or {
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        },
        run=run,
        permission=permission,
    )


class TestSchemaValidation:
    def test_valid_args_pass(self) -> None:
        assert validate_schema(_tool().input_schema, {"msg": "hi"}) is None

    def test_missing_required_rejected(self) -> None:
        err = validate_schema(_tool().input_schema, {})
        assert err is not None and "invalid arguments" in err

    def test_wrong_type_rejected(self) -> None:
        err = validate_schema(_tool().input_schema, {"msg": 42})
        assert err is not None and "msg" in err

    def test_broken_schema_is_harness_bug_message(self) -> None:
        err = validate_schema({"type": "object", "required": "not-a-list"}, {})
        assert err is not None and "harness bug" in err


class TestRegistry:
    def test_register_and_lookup(self) -> None:
        r = Registry([_tool()])
        assert len(r) == 1
        assert r.get("echo") is not None
        assert r.get("nope") is None
        assert [t.name for t in r] == ["echo"]

    def test_duplicate_name_fails_fast(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            Registry([_tool(), _tool()])

    def test_specs_stable_order(self) -> None:
        r = Registry([_tool("b"), _tool("a")])
        assert [s.name for s in r.specs()] == ["b", "a"]

    async def test_execute_happy_path(self) -> None:
        r = Registry([_tool()])
        res = await r.execute("echo", {"msg": "hi"}, "call-1")
        assert res.content == "echo:hi"
        assert not res.is_error
        assert res.tool_call_id == "call-1"

    async def test_unknown_tool_honest_error(self) -> None:
        r = Registry()
        res = await r.execute("ghost", {}, "c1")
        assert res.is_error and "unknown tool" in res.content

    async def test_schema_checked_before_run(self) -> None:
        ran = {"count": 0}

        async def spy(args: dict[str, Any]) -> str:
            ran["count"] += 1
            return "no debe correr"

        r = Registry([_tool(run=spy)])
        res = await r.execute("echo", {"msg": 123}, "c1")
        assert res.is_error and "invalid arguments" in res.content
        assert ran["count"] == 0  # la validación fue ANTES de ejecutar

    async def test_tool_exception_becomes_error_result(self) -> None:
        r = Registry([_tool(run=_boom)])
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.is_error and "RuntimeError" in res.content and "kaboom" in res.content

    async def test_error_prefix_marks_is_error(self) -> None:
        async def soft_fail(args: dict[str, Any]) -> str:
            return "ERROR: algo salió mal"

        r = Registry([_tool(run=soft_fail)])
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.is_error

    async def test_long_output_truncated_honestly(self) -> None:
        async def big(args: dict[str, Any]) -> str:
            return "x" * 60_000

        r = Registry([_tool(run=big)])
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.truncated and res.content.endswith("... [truncated]")
        assert len(res.content) < 60_000


class TestPermissionGate:
    async def test_deny_never_runs(self) -> None:
        ran = {"count": 0}

        async def spy(args: dict[str, Any]) -> str:
            ran["count"] += 1
            return "no"

        r = Registry([_tool(permission=Permission.DENY, run=spy)])
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.is_error and "denied by policy" in res.content
        assert ran["count"] == 0

    async def test_ask_without_approver_degrades_honestly(self) -> None:
        r = Registry([_tool(permission=Permission.ASK)])
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.is_error and "requires approval" in res.content

    async def test_ask_with_approver_yes_runs(self) -> None:
        async def yes(name: str, args: dict[str, Any]) -> bool:
            return True

        r = Registry([_tool(permission=Permission.ASK)], approver=yes)
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert not res.is_error and res.content == "echo:x"

    async def test_ask_with_approver_no_blocks(self) -> None:
        async def no(name: str, args: dict[str, Any]) -> bool:
            return False

        r = Registry([_tool(permission=Permission.ASK)], approver=no)
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.is_error and "not approved" in res.content

    async def test_approver_exception_is_honest_error(self) -> None:
        async def bad(name: str, args: dict[str, Any]) -> bool:
            raise OSError("TUI rota")

        r = Registry([_tool(permission=Permission.ASK)], approver=bad)
        res = await r.execute("echo", {"msg": "x"}, "c1")
        assert res.is_error and "approval failed" in res.content


class TestTruncate:
    def test_short_untouched(self) -> None:
        out, tr = truncate("hola")
        assert out == "hola" and not tr

    def test_long_cut_with_marker(self) -> None:
        out, tr = truncate("a" * 60_000)
        assert tr and out.endswith("... [truncated]")
