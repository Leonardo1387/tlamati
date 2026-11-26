"""D3 — MCP client.

Cliente mínimo del Model Context Protocol que envuelve cada tool remota como
un Tool local ASK + produces_untrusted. Dos transportes (misma interfaz):
stdio (``MCPClient``, D3) y Streamable HTTP (``MCPHTTPClient``, v2 — puerta
``url:`` con Unreal como primer consumidor real).
"""

from tlamati.mcp.client import (
    MCPClient,
    MCPError,
    MCPReport,
    MCPServerConfig,
    close_mcp,
    content_to_text,
    load_mcp_servers,
    parse_mcp_config,
)
from tlamati.mcp.http_client import MCPHTTPClient

__all__ = [
    "MCPClient",
    "MCPError",
    "MCPHTTPClient",
    "MCPReport",
    "MCPServerConfig",
    "close_mcp",
    "content_to_text",
    "load_mcp_servers",
    "parse_mcp_config",
]
