"""v2 — MCPHTTPClient tests: MockTransport emulando el servidor Unreal, cero red.

El handler replica el comportamiento MEDIDO contra el Unreal vivo
(HANDOFF_V2_MCP_HTTP.md §1): sid obligatorio tras initialize (400/-32600 sin
él), Accept dual, JSON puro o SSE, notifications sin cuerpo (202), DELETE de
cierre. Cubre los 12 casos del dimensionamiento.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from tlamati.mcp.client import MCPServerConfig, load_mcp_servers, parse_mcp_config
from tlamati.mcp.http_client import MCPHTTPClient
from tlamati.tools.registry import Permission

UE_TOOLS = [
    {
        "name": "call_tool",
        "description": "llama una tool de un toolset",
        "inputSchema": {
            "type": "object",
            "properties": {
                "toolset_name": {"type": "string"},
                "tool_name": {"type": "string"},
                "arguments": {"type": "object"},
            },
            "required": ["toolset_name", "tool_name"],
        },
    },
    {
        "name": "describe_toolset",
        "description": "describe un toolset",
        "inputSchema": {"type": "object", "properties": {"toolset_name": {"type": "string"}}},
    },
    {"name": "list_toolsets", "description": "lista toolsets", "inputSchema": {"type": "object"}},
]


class FakeUEServer:
    """Servidor MCP HTTP fake con el contrato medido del Unreal 5.8.4."""

    def __init__(
        self,
        *,
        sse: bool = False,
        require_sid: bool = True,
        fail_first_with_400: int = 0,
        dead: bool = False,
        slow: bool = False,
        tools: list[dict[str, Any]] | None = None,
        call_result: dict[str, Any] | None = None,
        delete_fails: bool = False,
    ) -> None:
        self.sse = sse
        self.require_sid = require_sid
        self.fail_first_with_400 = fail_first_with_400  # renegocio de sid
        self.dead = dead
        self.slow = slow
        self.tools = UE_TOOLS if tools is None else tools
        self.call_result = call_result or {
            "content": [{"type": "text", "text": "OK-RESPUESTA"}],
            "isError": False,
        }
        self.delete_fails = delete_fails
        self.sid = "sid-fake-123"
        self.requests: list[httpx.Request] = []
        self.post_count = 0
        self.deleted = False
        self.concurrent = 0
        self.max_concurrent = 0

    def _respond(self, payload: Any, status: int = 200) -> httpx.Response:
        headers = {"Content-Type": "application/json;charset=utf-8"}
        if status == 200 and self.require_sid and payload is not None:
            headers["Mcp-Session-Id"] = self.sid
        if payload is None:
            return httpx.Response(status, content=b"", headers=headers)
        body = json.dumps(payload).encode()
        if self.sse:
            # SSE comparte los mismos headers (incluido Mcp-Session-Id)
            headers = {**headers, "Content-Type": "text/event-stream"}
            body = b"event: message\ndata: " + body + b"\n\n"
        return httpx.Response(status, content=body, headers=headers)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "DELETE":
            self.deleted = True
            if self.delete_fails:
                raise httpx.ConnectError("server gone")
            return httpx.Response(204)
        # control de concurrencia (el lock del cliente debe impedir >1)
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            if self.dead:
                raise httpx.ConnectError("connection refused")
            if self.slow:
                import time

                time.sleep(0.05)  # dentro del handler sync: bloquea el "POST"
            self.post_count += 1
            msg = json.loads(request.content)
            sid = request.headers.get("Mcp-Session-Id")
            method = msg.get("method")
            has_id = "id" in msg
            # initialize es el que OTORGA el sid — nunca lo exige (medido real)
            if self.require_sid and has_id and method != "initialize" and sid != self.sid:
                return self._respond(
                    {
                        "jsonrpc": "2.0",
                        "id": msg.get("id"),
                        "error": {"code": -32600, "message": "Missing required Mcp-Session-Id"},
                    },
                    status=400,
                )
            if (
                self.fail_first_with_400
                and self.post_count > self.fail_first_with_400
                and sid == "sid-viejo"
            ):
                return self._respond(
                    {
                        "jsonrpc": "2.0",
                        "id": msg.get("id"),
                        "error": {"code": -32600, "message": "Session expired"},
                    },
                    status=400,
                )
            if method == "initialize":
                return self._respond(
                    {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "result": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "serverInfo": {"name": "UnrealEditorMCP", "version": "5.8.4"},
                        },
                    }
                )
            if method == "notifications/initialized":
                return self._respond(None, status=202)
            if method == "tools/list":
                return self._respond(
                    {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": self.tools}}
                )
            if method == "tools/call":
                return self._respond(
                    {"jsonrpc": "2.0", "id": msg["id"], "result": self.call_result}
                )
            return self._respond(
                {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "error": {"code": -32601, "message": f"method desconocido {method}"},
                },
                status=200,
            )
        finally:
            self.concurrent -= 1


def _client(server: FakeUEServer, timeout: float = 10.0) -> MCPHTTPClient:
    cfg = MCPServerConfig(name="unreal", url="http://127.0.0.1:8000/mcp", call_timeout_s=timeout)
    return MCPHTTPClient(cfg, transport=httpx.MockTransport(server.handler))


# ---- 1. handshake completo -------------------------------------------------


class TestHandshake:
    async def test_full_handshake_captures_sid_and_tools(self) -> None:
        s = FakeUEServer()
        c = _client(s)
        await c.connect()
        assert [t["name"] for t in c.tools] == [
            "call_tool",
            "describe_toolset",
            "list_toolsets",
        ]  # orden estable
        assert c.server_info == "UnrealEditorMCP 5.8.4"
        methods = [json.loads(r.content)["method"] for r in s.requests]
        assert methods == ["initialize", "notifications/initialized", "tools/list"]

    async def test_headers_accept_dual_and_origin(self) -> None:
        s = FakeUEServer()
        c = _client(s)
        await c.connect()
        h = s.requests[0].headers
        assert h["Accept"] == "application/json, text/event-stream"
        assert h["Origin"] == "http://127.0.0.1:8000"
        assert "tlamati" in h["User-Agent"]

    async def test_sid_sent_after_initialize(self) -> None:
        s = FakeUEServer()
        c = _client(s)
        await c.connect()
        # initialize SIN sid; el resto CON sid
        assert "Mcp-Session-Id" not in s.requests[0].headers
        for r in s.requests[1:]:
            assert r.headers["Mcp-Session-Id"] == "sid-fake-123"

    async def test_sse_response_parsed_identically(self) -> None:
        s = FakeUEServer(sse=True)
        c = _client(s)
        await c.connect()
        assert len(c.tools) == 3  # SSE no cambia nada para el cliente
        out = await c.call_tool("list_toolsets", {})
        assert out == "OK-RESPUESTA"


# ---- 2/3. sid caduco → renegocio automático --------------------------------


class TestSessionRenegotiation:
    async def test_expired_sid_renegotiated_once(self) -> None:
        s = FakeUEServer()
        c = _client(s)
        await c.connect()
        c._sid = "sid-viejo"  # simula: el servidor reinició, nuestro sid caducó
        s.fail_first_with_400 = -1  # desactiva el fail (usamos sid-viejo check)
        out = await c.call_tool("list_toolsets", {})
        assert out == "OK-RESPUESTA"  # renegoció y reintentó con éxito
        assert c._sid == "sid-fake-123"

    async def test_renegotiation_failure_is_honest_error(self) -> None:
        s = FakeUEServer(dead=False)
        c = _client(s)
        await c.connect()
        # servidor muere justo para el renegocio
        s.dead = True
        c._sid = "sid-viejo"
        out = await c.call_tool("list_toolsets", {})
        assert out.startswith("ERROR: servidor MCP 'unreal'")


# ---- 4. content_to_text compartido ------------------------------------------


class TestContentShared:
    async def test_iserror_becomes_error_string(self) -> None:
        s = FakeUEServer(
            call_result={"content": [{"type": "text", "text": "tool falló"}], "isError": True}
        )
        c = _client(s)
        await c.connect()
        out = await c.call_tool("call_tool", {"toolset_name": "x", "tool_name": "y"})
        assert out == "ERROR: tool falló"

    async def test_structured_content_serialized(self) -> None:
        s = FakeUEServer(
            call_result={
                "content": [{"type": "text", "text": "ok"}],
                "structuredContent": {"actor_id": 42},
                "isError": False,
            }
        )
        c = _client(s)
        await c.connect()
        out = await c.call_tool("call_tool", {"toolset_name": "x", "tool_name": "y"})
        assert "ok" in out and '"actor_id": 42' in out


# ---- 5/6. timeouts y red ----------------------------------------------------


class TestNetworkFailures:
    async def test_dead_server_is_mcperror_not_exception(self) -> None:
        s = FakeUEServer(dead=True)
        c = _client(s)
        with pytest.raises(Exception) as ei:
            await c.connect()
        assert ei.type.__name__ == "MCPError"
        assert "fallo de red" in str(ei.value)

    async def test_timeout_is_mcperror(self) -> None:
        def slow_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow")

        cfg = MCPServerConfig(name="slow", url="http://x/mcp", call_timeout_s=1.0)
        c = MCPHTTPClient(cfg, transport=httpx.MockTransport(slow_handler))
        with pytest.raises(Exception) as ei:
            await c.connect()
        assert "expiró" in str(ei.value)


# ---- 7. close ----------------------------------------------------------------


class TestClose:
    async def test_close_sends_delete_with_sid(self) -> None:
        s = FakeUEServer()
        c = _client(s)
        await c.connect()
        await c.close()
        assert s.deleted
        delete_req = next(r for r in s.requests if r.method == "DELETE")
        assert delete_req.headers["Mcp-Session-Id"] == "sid-fake-123"

    async def test_close_failure_never_raises(self) -> None:
        s = FakeUEServer(delete_fails=True)
        c = _client(s)
        await c.connect()
        await c.close()  # no debe explotar
        assert c._sid is None

    async def test_close_without_connect_is_noop(self) -> None:
        s = FakeUEServer()
        c = _client(s)
        await c.close()
        assert not s.deleted


# ---- 8. llamadas en serie (lock) ---------------------------------------------


class TestSerialCalls:
    async def test_concurrent_calls_serialize(self) -> None:
        import asyncio

        s = FakeUEServer(slow=True)
        c = _client(s)
        await c.connect()
        await asyncio.gather(*[c.call_tool("list_toolsets", {}) for _ in range(4)])
        assert s.max_concurrent == 1


# ---- 9/10. config parse -------------------------------------------------------


class TestConfigParse:
    def test_url_entry_parsed(self) -> None:
        raw = {"servers": [{"name": "unreal", "url": "http://127.0.0.1:8000/mcp"}]}
        configs, errors = parse_mcp_config(raw)
        assert errors == []
        assert configs == [MCPServerConfig(name="unreal", url="http://127.0.0.1:8000/mcp")]
        assert configs[0].command == ()

    def test_command_and_url_together_rejected(self) -> None:
        raw = {"servers": [{"name": "x", "command": ["uvx", "y"], "url": "http://a/mcp"}]}
        configs, errors = parse_mcp_config(raw)
        assert configs == []
        assert "mutuamente excluyentes" in errors[0]

    def test_bad_scheme_rejected(self) -> None:
        raw = {"servers": [{"name": "x", "url": "file:///etc/passwd"}]}
        configs, errors = parse_mcp_config(raw)
        assert configs == []
        assert "http://" in errors[0]

    def test_missing_both_rejected(self) -> None:
        raw = {"servers": [{"name": "x"}]}
        configs, errors = parse_mcp_config(raw)
        assert configs == []
        assert "falta 'command'" in errors[0]

    def test_stdio_entry_unchanged_regression(self) -> None:
        """Regresión: entradas stdio existentes parsean byte-idéntico (D3)."""
        raw = {"servers": [{"name": "rea", "command": ["npx", "-y", "@morluto/rea-mcp"]}]}
        configs, errors = parse_mcp_config(raw)
        assert errors == []
        assert configs[0].name == "rea"
        assert configs[0].command == ("npx", "-y", "@morluto/rea-mcp")
        assert configs[0].url is None


# ---- 11. integración make_mcp_tools -------------------------------------------


class TestToolWrapping:
    async def test_http_client_tools_wrapped_ask_untrusted(self) -> None:
        from tlamati.mcp.client import make_mcp_tools

        s = FakeUEServer()
        c = _client(s)
        await c.connect()
        tools = make_mcp_tools(c)  # duck-typing: misma interfaz que MCPClient
        assert [t.name for t in tools] == [
            "mcp_unreal_call_tool",
            "mcp_unreal_describe_toolset",
            "mcp_unreal_list_toolsets",
        ]
        for t in tools:
            assert t.permission is Permission.ASK
            assert t.produces_untrusted is True
        out = await tools[2].run({})
        assert out == "OK-RESPUESTA"


# ---- 12. fail-soft en load_mcp_servers ----------------------------------------


class TestLoadFailSoft:
    async def test_dead_http_server_reported_run_continues(self) -> None:
        """Servidor HTTP muerto → error honesto en MCPReport, corrida sin él."""
        dead = FakeUEServer(dead=True)
        cfg = MCPServerConfig(name="unreal", url="http://127.0.0.1:8000/mcp")

        class Patched(MCPHTTPClient):
            def __init__(self, config: Any, **kw: Any) -> None:
                super().__init__(config, transport=httpx.MockTransport(dead.handler), **kw)

        # load_mcp_servers importa MCPHTTPClient desde http_client dentro de la
        # función → parchar el atributo del módulo funciona.
        import tlamati.mcp.http_client as hc

        old = hc.MCPHTTPClient
        hc.MCPHTTPClient = Patched  # type: ignore[misc]
        try:
            report = await load_mcp_servers([cfg])
        finally:
            hc.MCPHTTPClient = old  # type: ignore[misc]
        assert report.clients == []
        assert report.tools == []
        assert len(report.errors) == 1
        assert report.errors[0][0] == "unreal"

    async def test_load_dispatches_url_to_http_client(self) -> None:
        s = FakeUEServer()
        import tlamati.mcp.http_client as hc

        old = hc.MCPHTTPClient

        class Patched(old):  # type: ignore[misc, valid-type]
            def __init__(self, config: Any, **kw: Any) -> None:
                super().__init__(config, transport=httpx.MockTransport(s.handler), **kw)

        hc.MCPHTTPClient = Patched  # type: ignore[misc]
        try:
            report = await load_mcp_servers(
                [MCPServerConfig(name="unreal", url="http://127.0.0.1:8000/mcp")]
            )
        finally:
            hc.MCPHTTPClient = old  # type: ignore[misc]
        assert len(report.clients) == 1
        assert len(report.tools) == 3
        assert report.errors == []
        await report.clients[0].close()
