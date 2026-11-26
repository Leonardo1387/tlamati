"""D3 — MCP client stdio mínimo: el enchufe universal (F8, PRD SHOULD).

Model Context Protocol (modelcontextprotocol.io): JSON-RPC 2.0 sobre stdio.
Ciclo de vida: subprocess del servidor → ``initialize`` → notificación
``notifications/initialized`` → ``tools/list`` → cada tool remota se envuelve
como un Tool local. Reglas innegociables del handoff D3:

- NUNCA auto-descubrir servidores: un MCP en el repo de un tercero es código
  ajeno que además EJECUTA UN PROCESO. Solo servidores declarados en
  tlamati.yaml (``mcp.servers``) o ``--mcp-config``.
- ``permission=ASK`` SIEMPRE (la escalera de policy puede endurecer a deny,
  NUNCA relajar a auto — ni por config).
- ``produces_untrusted=True`` SIEMPRE: el contenido viene de un proceso de
  terceros → tras consumir un resultado MCP, el egreso escala a ASK
  (trifecta B4).
- Fail-soft total (patrón C3/C6/D2): servidor que no arranca, handshake
  inválido o tools/list roto = aviso honesto por stderr + corrida SIN ese
  servidor. Un servidor colgado NUNCA cuelga la corrida (timeout por llamada
  + cierre terminate→wait→kill).
- Prefijo: las tools MCP son visibles al modelo (a diferencia de los plugins
  D2) → añadir/quitar servidores MCP SÍ cambia el prefijo cacheable. Es
  esperado: es configuración de corrida, estable DENTRO de la corrida. Se
  añaden AL FINAL del tool_list en orden estable por (servidor, tool).
- Compaction: NO entran a DEFAULT_COMPACTABLE_TOOLS — un resultado MCP puede
  no ser re-obtenible (side-effect o servidor con estado).
- Auditoría: sin trabajo extra — son Tools normales; el plugin interno D2 las
  registra en el ledger automáticamente.

Puerta ``url:`` (Streamable HTTP) — CONSTRUIDA en v2 (26-nov): la config acepta
``url:`` además de ``command:`` (XOR, nunca ambos). El transporte HTTP vive en
``mcp/http_client.py`` (MCPHTTPClient, misma interfaz pública que MCPClient);
``load_mcp_servers`` elige por config. Primer consumidor real: el MCP oficial
de Unreal (127.0.0.1:8000/mcp, protocolVersion 2025-06-18, Mcp-Session-Id
obligatorio tras initialize — evidencia real en HANDOFF_V2_MCP_HTTP.md §1).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from tlamati import __version__
from tlamati.tools.registry import Permission, Tool

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_CALL_TIMEOUT_S = 60.0
CLOSE_TIMEOUT_S = 5.0


class MCPError(Exception):
    """Fallo honesto de un servidor MCP (arranque, handshake o llamada)."""


def content_to_text(result: dict[str, Any]) -> str:
    """Lógica de PROTOCOLO (no de transporte): content[] + structuredContent
    → string. Compartida por MCPClient (stdio) y MCPHTTPClient (v2 HTTP)."""
    parts: list[str] = []
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
    structured = result.get("structuredContent")
    if structured is not None:
        parts.append(json.dumps(structured, ensure_ascii=False))
    return "\n".join(parts) if parts else ""


@dataclass(frozen=True)
class MCPServerConfig:
    """Un servidor declarado por el dueño. ``command`` es argv (sin shell);
    ``url`` es Streamable HTTP (v2). Exactamente uno de los dos (XOR)."""

    name: str
    command: tuple[str, ...] = ()
    url: str | None = None
    call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S


class MCPTransport(Protocol):
    """Interfaz común de los dos transportes (stdio MCPClient, HTTP
    MCPHTTPClient v2). Duck-typing tipado: make_mcp_tools/load/close aceptan
    cualquiera de los dos sin herencia compartida."""

    config: MCPServerConfig
    tools: list[dict[str, Any]]
    server_info: str

    async def connect(self) -> None: ...
    async def call_tool(self, name: str, args: dict[str, Any]) -> str: ...
    async def close(self) -> None: ...


@dataclass
class MCPReport:
    """Evidencia honesta de la carga (log del CLI + tests)."""

    clients: list[MCPTransport] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (servidor, motivo)


def parse_mcp_config(raw: Any) -> tuple[list[MCPServerConfig], list[str]]:
    """Parsea el bloque ``mcp:`` del yaml. Devuelve (configs válidas, errores
    honestos por entrada inválida — nunca raise, patrón fail-soft)."""
    errors: list[str] = []
    configs: list[MCPServerConfig] = []
    if raw is None:
        return configs, errors
    if not isinstance(raw, dict):
        return configs, ["la sección 'mcp' debe ser un mapa"]
    servers = raw.get("servers")
    if servers is None:
        return configs, errors
    if not isinstance(servers, list):
        return configs, ["'mcp.servers' debe ser una lista"]
    for i, entry in enumerate(servers):
        if not isinstance(entry, dict):
            errors.append(f"mcp.servers[{i}]: debe ser un mapa con name y command o url")
            continue
        name = entry.get("name")
        command = entry.get("command")
        url = entry.get("url")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"mcp.servers[{i}]: 'name' ausente o vacío")
            continue
        has_command = isinstance(command, list) and bool(command)
        has_url = isinstance(url, str) and bool(url.strip())
        if command is not None and url is not None:
            errors.append(
                f"mcp.servers[{i}] ({name}): 'command' y 'url' son mutuamente "
                "excluyentes (stdio XOR Streamable HTTP)"
            )
            continue
        argv: tuple[str, ...] = ()
        clean_url: str | None = None
        if has_command:
            assert isinstance(command, list)
            if not all(isinstance(c, str) for c in command):
                errors.append(f"mcp.servers[{i}] ({name}): 'command' debe ser argv de strings")
                continue
            argv = tuple(command)
        elif has_url:
            assert isinstance(url, str)
            if not url.strip().lower().startswith(("http://", "https://")):
                errors.append(f"mcp.servers[{i}] ({name}): 'url' debe ser http:// o https://")
                continue
            clean_url = url.strip()
        else:
            errors.append(f"mcp.servers[{i}] ({name}): falta 'command' (argv stdio) o 'url' (HTTP)")
            continue
        timeout = DEFAULT_CALL_TIMEOUT_S
        raw_timeout = entry.get("timeout_s")
        if raw_timeout is not None:
            try:
                timeout = float(raw_timeout)
                if timeout <= 0:
                    raise ValueError("timeout_s debe ser > 0")
            except (TypeError, ValueError):
                errors.append(
                    f"mcp.servers[{i}] ({name}): timeout_s inválido — se usa "
                    f"{DEFAULT_CALL_TIMEOUT_S:.0f}s"
                )
                timeout = DEFAULT_CALL_TIMEOUT_S
        configs.append(
            MCPServerConfig(name=name.strip(), command=argv, url=clean_url, call_timeout_s=timeout)
        )
    return configs, errors


class MCPClient:
    """Cliente JSON-RPC 2.0 sobre stdio de UN servidor MCP.

    Uso: ``await client.connect()`` (handshake + tools/list), luego
    ``client.tools`` / ``await client.call_tool(name, args)`` y al final
    ``await client.close()`` (terminate → wait → kill: un servidor colgado
    nunca cuelga la corrida)."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.tools: list[dict[str, Any]] = []
        self.server_info: str = ""
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def connect(self) -> None:
        """Arranca el subprocess y hace el handshake. Raise MCPError honesto
        en cualquier fallo (el llamador — load_mcp_servers — decide seguir)."""
        cfg = self.config
        try:
            # stderr se hereda: los logs del servidor son visibles (honestos),
            # y no hay pipe extra que pueda deadlockear.
            self._proc = await asyncio.create_subprocess_exec(
                *cfg.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
        except OSError as e:
            raise MCPError(f"no se pudo arrancar el servidor: {e}") from e

        try:
            init = await self._request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "tlamati", "version": __version__},
                },
                timeout=cfg.call_timeout_s,
            )
        except MCPError:
            await self.close()
            raise
        info = init.get("serverInfo") if isinstance(init, dict) else None
        if isinstance(info, dict):
            self.server_info = f"{info.get('name', '?')} {info.get('version', '')}".strip()
        await self._notify("notifications/initialized")
        try:
            listed = await self._request("tools/list", {}, timeout=cfg.call_timeout_s)
        except MCPError:
            await self.close()
            raise
        raw_tools = listed.get("tools") if isinstance(listed, dict) else None
        if not isinstance(raw_tools, list):
            await self.close()
            raise MCPError("tools/list no devolvió una lista de tools")
        # Orden estable por nombre de tool (cache sagrada: el prefijo solo
        # cambia si cambia el conjunto de tools, no su orden de llegada).
        self.tools = sorted(
            (t for t in raw_tools if isinstance(t, dict) and isinstance(t.get("name"), str)),
            key=lambda t: str(t["name"]),
        )

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """tools/call → contenido como string. isError del protocolo →
        resultado con prefijo ERROR: (ToolResult is_error honesto).
        structured content → JSON serializado."""
        try:
            result = await self._request(
                "tools/call", {"name": name, "arguments": args}, timeout=self.config.call_timeout_s
            )
        except MCPError as e:
            return f"ERROR: servidor MCP {self.config.name!r}: {e}"
        if not isinstance(result, dict):
            return "ERROR: respuesta MCP inválida (se esperaba un objeto result)"
        if result.get("isError"):
            return f"ERROR: {self._content_to_text(result)}"
        return self._content_to_text(result)

    @staticmethod
    def _content_to_text(result: dict[str, Any]) -> str:
        # v2: la lógica vive en content_to_text (módulo) — compartida con HTTP.
        return content_to_text(result)

    async def close(self) -> None:
        """Cierre limpio: terminate → wait con timeout → kill. Nunca raise."""
        proc = self._proc
        self._proc = None
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=CLOSE_TIMEOUT_S)
        except (TimeoutError, ProcessLookupError):
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=CLOSE_TIMEOUT_S)
            except (TimeoutError, ProcessLookupError, OSError):
                pass
        except Exception:  # cualquier otro fallo de cierre = honesto y sigue
            pass

    async def _request(self, method: str, params: dict[str, Any], *, timeout: float) -> Any:
        """JSON-RPC request/response secuencial (una llamada a la vez). Las
        notificaciones del servidor entre medias se ignoran (sin id)."""
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise MCPError("el servidor no está conectado")
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        try:
            proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            raise MCPError(f"stdin roto al enviar {method}: {e}") from e

        async def _read_response() -> Any:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    raise MCPError(f"el servidor cerró stdout durante {method}")
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue  # basura no-JSON por stdout: se ignora (honesto)
                if not isinstance(msg, dict) or msg.get("id") != req_id:
                    continue  # notificaciones o mensajes ajenos: skip
                if "error" in msg:
                    err = msg["error"]
                    detail = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    raise MCPError(f"{method} devolvió error: {detail}")
                return msg.get("result")

        try:
            return await asyncio.wait_for(_read_response(), timeout=timeout)
        except TimeoutError as e:
            raise MCPError(f"{method} expiró tras {timeout:.0f}s (servidor colgado)") from e

    async def _notify(self, method: str) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise MCPError("el servidor no está conectado")
        payload = {"jsonrpc": "2.0", "method": method}
        try:
            proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            raise MCPError(f"stdin roto al enviar {method}: {e}") from e


def make_mcp_tools(client: MCPTransport) -> list[Tool]:
    """Envuelve cada tool remota como Tool local: nombre ``mcp_<server>_<tool>``
    (prefijo anti-colisiones), ASK + produces_untrusted SIEMPRE (innegociable,
    handoff D3), input_schema = el que declare el servidor (validate_schema B1
    ya lo valida antes de llamar; schema roto del servidor = error honesto
    "harness bug", no crash)."""
    server = client.config.name
    wrapped: list[Tool] = []
    for raw in client.tools:
        remote_name = str(raw["name"])
        schema = raw.get("inputSchema")
        if not isinstance(schema, dict):
            schema = {"type": "object"}
        description = str(raw.get("description") or f"(servidor MCP {server} no dio descripción)")

        async def _run(
            args: dict[str, Any], _client: MCPTransport = client, _remote: str = remote_name
        ) -> str:
            return await _client.call_tool(_remote, args)

        wrapped.append(
            Tool(
                name=f"mcp_{server}_{remote_name}",
                description=description,
                input_schema=schema,
                run=_run,
                permission=Permission.ASK,
                produces_untrusted=True,
            )
        )
    return wrapped


async def load_mcp_servers(
    configs: Sequence[MCPServerConfig],
) -> MCPReport:
    """Arranca cada servidor en orden de config. Fail-soft total: servidor que
    falla = error honesto anotado + aviso stderr + corrida SIN ese servidor."""
    report = MCPReport()
    for cfg in configs:
        client: MCPTransport
        if cfg.url:
            from tlamati.mcp.http_client import MCPHTTPClient

            client = MCPHTTPClient(cfg)
        else:
            client = MCPClient(cfg)
        try:
            await client.connect()
        except MCPError as e:
            report.errors.append((cfg.name, str(e)))
            print(f"[mcp] servidor {cfg.name!r} no cargó: {e} — corrida SIN él", file=sys.stderr)
            continue
        except Exception as e:  # nunca romper la corrida por un servidor
            report.errors.append((cfg.name, f"{type(e).__name__}: {e}"))
            print(
                f"[mcp] servidor {cfg.name!r} falló inesperadamente "
                f"({type(e).__name__}: {e}) — corrida SIN él",
                file=sys.stderr,
            )
            await client.close()
            continue
        report.clients.append(client)
        report.tools.extend(make_mcp_tools(client))
        print(f"[mcp] server={cfg.name} tools={len(client.tools)}", file=sys.stderr)
    return report


async def close_mcp(clients: Sequence[MCPTransport]) -> None:
    """Cierra todos los servidores al terminar la corrida (nunca raise)."""
    for client in clients:
        await client.close()
