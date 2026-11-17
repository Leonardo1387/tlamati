"""D3 — MCP client stdio: handshake ok/roto, tools/list vacío, call
ok/error/timeout, ASK + produces_untrusted innegociables, servidor colgado,
config fail-soft, orden estable, cierre limpio.

Los tests usan FakeMCPServer (tests/fake_mcp_server.py): un PROCESO real que
habla JSON-RPC por stdio — sin mocks en memoria, se cubre subprocess+pipes.
asyncio_mode=auto del proyecto (sin @pytest.mark.anyio)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from tlamati.mcp.client import (
    MCPClient,
    MCPError,
    MCPServerConfig,
    close_mcp,
    make_mcp_tools,
    parse_mcp_config,
)
from tlamati.tools.registry import Permission, Registry

FAKE = str(Path(__file__).parent / "fake_mcp_server.py")


def _cfg(mode: str = "ok", timeout_s: float = 10.0, name: str = "fake") -> MCPServerConfig:
    return MCPServerConfig(
        name=name, command=(sys.executable, FAKE, mode), call_timeout_s=timeout_s
    )


async def _connect(cfg: MCPServerConfig) -> MCPClient:
    client = MCPClient(cfg)
    await client.connect()
    return client


class TestHandshake:
    async def test_connect_ok_lists_tools_sorted(self) -> None:
        client = await _connect(_cfg())
        try:
            assert client.server_info.startswith("fake-mcp")
            assert [t["name"] for t in client.tools] == ["add", "echo"]  # orden estable
        finally:
            await client.close()

    async def test_bad_handshake_raises_honest_error(self) -> None:
        try:
            await _connect(_cfg("bad_handshake"))
            raise AssertionError("debía fallar")
        except MCPError as e:
            assert "no te entiendo" in str(e)

    async def test_garbage_init_raises(self) -> None:
        try:
            await _connect(_cfg("garbage_init"))
            raise AssertionError("debía fallar")
        except MCPError as e:
            assert "initialize" in str(e)

    async def test_die_immediately_fail_soft(self) -> None:
        try:
            await _connect(_cfg("die_immediately"))
            raise AssertionError("debía fallar")
        except MCPError:
            pass  # stdout cerrado / exit 1 → error honesto, no crash

    async def test_hang_on_init_times_out(self) -> None:
        try:
            await _connect(_cfg("hang_on_init", timeout_s=1.0))
            raise AssertionError("debía fallar")
        except MCPError as e:
            assert "expiró" in str(e)

    async def test_empty_tools_list_is_ok(self) -> None:
        client = await _connect(_cfg("empty_tools"))
        try:
            assert client.tools == []
        finally:
            await client.close()


class TestToolCall:
    async def test_call_ok_returns_text(self) -> None:
        client = await _connect(_cfg())
        try:
            out = await client.call_tool("echo", {"text": "hola"})
            assert out == "eco remoto: hola"
            assert await client.call_tool("add", {"a": 2, "b": 3}) == "5"
        finally:
            await client.close()

    async def test_call_isError_becomes_ERROR_prefix(self) -> None:
        client = await _connect(_cfg("error_on_call"))
        try:
            out = await client.call_tool("echo", {"text": "x"})
            assert out.startswith("ERROR:")
            assert "fallé" in out
        finally:
            await client.close()

    async def test_call_timeout_honest(self) -> None:
        client = await _connect(_cfg("hang_on_call", timeout_s=1.0))
        try:
            out = await client.call_tool("echo", {"text": "x"})
            assert out.startswith("ERROR:")
            assert "expiró" in out
        finally:
            await client.close()

    async def test_close_terminates_process(self) -> None:
        client = await _connect(_cfg())
        proc = client._proc
        assert proc is not None and proc.returncode is None
        await client.close()
        assert proc.returncode is not None  # el servidor murió con el cliente


class TestToolWrapping:
    async def test_ask_and_untrusted_are_nonnegotiable(self) -> None:
        client = await _connect(_cfg())
        try:
            tools = make_mcp_tools(client)
            assert [t.name for t in tools] == ["mcp_fake_add", "mcp_fake_echo"]
            for t in tools:
                assert t.permission is Permission.ASK
                assert t.produces_untrusted is True
        finally:
            await client.close()

    async def test_registry_execute_routes_to_server(self) -> None:
        client = await _connect(_cfg())
        try:
            reg = Registry(make_mcp_tools(client))
            # sin approver → ASK devuelve error honesto (nunca yolo)
            res = await reg.execute("mcp_fake_echo", {"text": "x"}, "t1")
            assert res.is_error and "requires approval" in res.content
        finally:
            await client.close()

    async def test_registry_execute_with_approver_marks_untrusted(self) -> None:
        client = await _connect(_cfg())

        async def approve(name: str, args: dict[str, Any]) -> bool:
            return True

        try:
            reg = Registry(make_mcp_tools(client), approver=approve)
            res = await reg.execute("mcp_fake_echo", {"text": "mundo"}, "t2")
            assert not res.is_error
            assert res.content == "eco remoto: mundo"
            assert res.untrusted is True  # trifecta B4 activada
        finally:
            await client.close()

    async def test_schema_from_server_validates_args(self) -> None:
        client = await _connect(_cfg())

        async def approve(name: str, args: dict[str, Any]) -> bool:
            return True

        try:
            reg = Registry(make_mcp_tools(client), approver=approve)
            # 'text' requerido por el schema del servidor → validación B1 local
            res = await reg.execute("mcp_fake_echo", {}, "t3")
            assert res.is_error and "invalid arguments" in res.content
        finally:
            await client.close()


class TestConfig:
    def test_parse_ok(self) -> None:
        configs, errors = parse_mcp_config(
            {"servers": [{"name": "rea", "command": ["npx", "-y", "@morluto/rea-mcp"]}]}
        )
        assert errors == []
        assert configs == [MCPServerConfig(name="rea", command=("npx", "-y", "@morluto/rea-mcp"))]

    def test_parse_none_is_empty(self) -> None:
        assert parse_mcp_config(None) == ([], [])

    def test_parse_invalid_entries_fail_soft(self) -> None:
        configs, errors = parse_mcp_config(
            {
                "servers": [
                    "no-soy-mapa",
                    {"command": ["x"]},  # sin name
                    {"name": "sin-cmd"},  # sin command
                    {"name": "cmd-malo", "command": "npx foo"},  # no es lista
                    {"name": "ok", "command": ["true"], "timeout_s": "lento"},
                ]
            }
        )
        assert len(errors) == 5
        # el válido con timeout roto entra con default
        assert len(configs) == 1
        assert configs[0].name == "ok"
        assert configs[0].call_timeout_s == 60.0

    def test_parse_timeout_ok(self) -> None:
        configs, errors = parse_mcp_config(
            {"servers": [{"name": "s", "command": ["true"], "timeout_s": 5}]}
        )
        assert errors == []
        assert configs[0].call_timeout_s == 5.0


class TestFailSoftLoad:
    async def test_dead_server_does_not_break_others(self) -> None:
        from tlamati.mcp.client import load_mcp_servers

        report = await load_mcp_servers(
            [_cfg("die_immediately", name="muerto"), _cfg("ok", name="vivo")]
        )
        try:
            assert [c.config.name for c in report.clients] == ["vivo"]
            assert [n for n, _ in report.errors] == ["muerto"]
            assert [t.name for t in report.tools] == ["mcp_vivo_add", "mcp_vivo_echo"]
        finally:
            await close_mcp(report.clients)

    async def test_close_mcp_never_raises(self) -> None:
        client = await _connect(_cfg())
        await close_mcp([client])
        await close_mcp([client])  # doble cierre = inocuo
        await close_mcp([])  # lista vacía = inocuo
