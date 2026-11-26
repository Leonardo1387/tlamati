"""v2 — MCPHTTPClient: transporte Streamable HTTP (la puerta ``url:`` de D3).

Primer consumidor real: el MCP oficial de Unreal Engine (5.8.4,
127.0.0.1:8000/mcp). Evidencia recogida con el editor VIVO (26-nov,
HANDOFF_V2_MCP_HTTP.md §1):

- ``initialize`` → HTTP 200, ``protocolVersion: 2025-06-18``, devuelve header
  ``Mcp-Session-Id``; TODA llamada posterior sin ese header → 400 (JSON-RPC
  -32600). El cliente captura el sid y lo manda siempre.
- ``Accept: application/json, text/event-stream`` obligatorio; la respuesta
  llega como JSON puro O como SSE (``data: …``) — se parsean ambas.
- Llamadas EN SERIE (restricción medida del servidor Unreal): lock interno,
  nunca dos POST simultáneos.
- tools/list en Unreal devuelve 3 meta-tools (list_toolsets,
  describe_toolset, call_tool) — se envuelven TAL CUAL (la spec MCP es el
  contrato; aplanar toolsets sería speculative y reventaría el prefijo).
- Header ``Origin``: opcional en 5.8.4 (probado con y sin → 200 ambos) pero
  la spec lo recomienda; se envía derivado de la url. Barato y compatible.

Misma interfaz pública que MCPClient (duck-typing, sin herencia: stdio tiene
subprocess, HTTP no): ``connect()`` / ``tools`` / ``server_info`` /
``call_tool()`` / ``close()`` / ``config``. Reglas D3 intactas: fail-soft,
MCPError honesto, ASK + produces_untrusted los aplica make_mcp_tools igual.

Sid caducado (el servidor reinició): UN renegocio automático por llamada
(initialize fresco + retry). Si vuelve a fallar → MCPError honesto. Nunca
un loop de renegocios.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from tlamati import __version__
from tlamati.mcp.client import MCPError, MCPServerConfig, content_to_text

PROTOCOL_VERSION_HTTP = "2025-06-18"  # el que negocia Unreal 5.8.4 (medido)
CLOSE_TIMEOUT_S = 5.0


def _origin_of(url: str) -> str:
    """Origin (scheme://host[:port]) derivado de la url del servidor."""
    p = urlparse(url)
    netloc = p.netloc
    return f"{p.scheme}://{netloc}"


def _parse_body(text: str) -> Any:
    """JSON puro o SSE (``data: …`` por líneas). Patrón probado contra el
    Unreal vivo (evidencia/mcp_ue.py del proyecto puente)."""
    stripped = text.lstrip()
    if stripped.startswith("data:") or "\ndata:" in text or "\r\ndata:" in text:
        parts = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = "\n".join(parts)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise MCPError(f"respuesta no-JSON del servidor: {text[:200]!r}") from e


class MCPHTTPClient:
    """Cliente MCP JSON-RPC 2.0 sobre Streamable HTTP de UN servidor.

    Uso idéntico a MCPClient: ``await connect()`` → ``tools`` /
    ``await call_tool(name, args)`` → ``await close()``.
    ``transport`` es solo para tests (httpx.MockTransport, cero red en CI).
    """

    def __init__(
        self, config: MCPServerConfig, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not config.url:
            raise MCPError(f"config de {config.name!r} sin url — transporte HTTP imposible")
        self.config = config
        self.tools: list[dict[str, Any]] = []
        self.server_info: str = ""
        self._sid: str | None = None
        self._next_id = 1
        self._lock = asyncio.Lock()  # llamadas EN SERIE (restricción medida)
        self._transport = transport

    # -- HTTP primitivas -------------------------------------------------

    def _headers(self) -> dict[str, str]:
        assert self.config.url is not None
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            # Identificación honesta + Origin (spec-recomendado, medido compatible)
            "User-Agent": f"tlamati/{__version__} (mcp-http)",
            "Origin": _origin_of(self.config.url),
        }
        if self._sid:
            h["Mcp-Session-Id"] = self._sid
        return h

    async def _post(self, payload: dict[str, Any], *, timeout: float) -> tuple[int, Any]:
        """POST JSON-RPC → (status, cuerpo parseado o None si vacío).
        Captura Mcp-Session-Id si el servidor lo manda. Raise MCPError en
        fallo de red/timeout (nunca excepción cruda al llamador)."""
        assert self.config.url is not None
        client_kwargs: dict[str, Any] = {"timeout": timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    self.config.url, content=json.dumps(payload), headers=self._headers()
                )
        except httpx.TimeoutException as e:
            method = str(payload.get("method", "?"))
            raise MCPError(f"{method} expiró tras {timeout:.0f}s (servidor colgado)") from e
        except httpx.HTTPError as e:
            raise MCPError(f"fallo de red HTTP: {type(e).__name__}: {e}") from e

        new_sid = response.headers.get("Mcp-Session-Id")
        if new_sid:
            self._sid = new_sid
        body = response.text
        if not body.strip():
            return response.status_code, None
        return response.status_code, _parse_body(body)

    async def _request(self, method: str, params: dict[str, Any], *, timeout: float) -> Any:
        """JSON-RPC request → result. Errores HTTP o JSON-RPC → MCPError
        honesto con el detalle del servidor."""
        req_id = self._next_id
        self._next_id += 1
        status, msg = await self._post(
            {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
            timeout=timeout,
        )
        if status >= 400:
            detail = ""
            if isinstance(msg, dict):
                err = msg.get("error")
                if isinstance(err, dict):
                    detail = str(err.get("message", ""))
            raise MCPError(f"{method} → HTTP {status}" + (f" ({detail})" if detail else ""))
        if not isinstance(msg, dict):
            raise MCPError(f"{method} devolvió cuerpo vacío o inválido")
        if "error" in msg:
            err = msg["error"]
            detail = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise MCPError(f"{method} devolvió error: {detail}")
        return msg.get("result")

    async def _notify(self, method: str) -> None:
        """Notificación (sin id): 2xx = OK, cuerpo vacío esperado."""
        status, _ = await self._post(
            {"jsonrpc": "2.0", "method": method}, timeout=self.config.call_timeout_s
        )
        if status >= 400:
            raise MCPError(f"notificación {method} → HTTP {status}")

    # -- ciclo de vida ----------------------------------------------------

    async def _handshake(self) -> None:
        """initialize → capturar sid → initialized → tools/list. Raise MCPError."""
        cfg = self.config
        init = await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION_HTTP,
                "capabilities": {},
                "clientInfo": {"name": "tlamati", "version": __version__},
            },
            timeout=cfg.call_timeout_s,
        )
        info = init.get("serverInfo") if isinstance(init, dict) else None
        if isinstance(info, dict):
            self.server_info = f"{info.get('name', '?')} {info.get('version', '')}".strip()
        await self._notify("notifications/initialized")
        listed = await self._request("tools/list", {}, timeout=cfg.call_timeout_s)
        raw_tools = listed.get("tools") if isinstance(listed, dict) else None
        if not isinstance(raw_tools, list):
            raise MCPError("tools/list no devolvió una lista de tools")
        # Orden estable por nombre (cache sagrada, igual que stdio).
        self.tools = sorted(
            (t for t in raw_tools if isinstance(t, dict) and isinstance(t.get("name"), str)),
            key=lambda t: str(t["name"]),
        )

    async def connect(self) -> None:
        """Handshake completo bajo lock. Raise MCPError honesto (el llamador —
        load_mcp_servers — decide seguir sin este servidor)."""
        async with self._lock:
            await self._handshake()

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """tools/call → string (content_to_text compartido con stdio).
        Sid caduco (400/-32600) → UN renegocio automático + retry."""
        async with self._lock:
            try:
                return await self._call_tool_once(name, args)
            except MCPError as e:
                if not self._is_session_error(e):
                    return f"ERROR: servidor MCP {self.config.name!r}: {e}"
                # servidor reiniciado: sid viejo inválido → handshake fresco
                try:
                    self._sid = None
                    await self._handshake()
                    return await self._call_tool_once(name, args)
                except MCPError as e2:
                    return f"ERROR: servidor MCP {self.config.name!r}: {e2} (tras renegociar)"

    async def _call_tool_once(self, name: str, args: dict[str, Any]) -> str:
        result = await self._request(
            "tools/call",
            {"name": name, "arguments": args},
            timeout=self.config.call_timeout_s,
        )
        if not isinstance(result, dict):
            raise MCPError("respuesta MCP inválida (se esperaba un objeto result)")
        if result.get("isError"):
            return f"ERROR: {content_to_text(result)}"
        return content_to_text(result)

    @staticmethod
    def _is_session_error(e: MCPError) -> bool:
        """400 con -32600 = sid ausente/caduco (medido contra Unreal vivo)."""
        s = str(e)
        return "HTTP 400" in s or "-32600" in s

    async def close(self) -> None:
        """DELETE de la sesión (spec Streamable HTTP). Fail-soft total:
        servidor que no lo soporta o ya murió → se ignora. Nunca raise."""
        if not self._sid:
            return
        assert self.config.url is not None
        sid, self._sid = self._sid, None
        headers = self._headers()
        headers["Mcp-Session-Id"] = sid
        client_kwargs: dict[str, Any] = {"timeout": CLOSE_TIMEOUT_S}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                await client.delete(self.config.url, headers=headers)
        except Exception:
            pass  # cierre honesto y silencioso: nunca rompe la corrida
