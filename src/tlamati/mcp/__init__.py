"""D3 — MCP client.

Cliente mínimo del Model Context Protocol (JSON-RPC 2.0 sobre stdio) que
envuelve cada tool remota como un Tool local ASK + produces_untrusted.
"""

from tlamati.mcp.client import (
    MCPClient,
    MCPError,
    MCPReport,
    MCPServerConfig,
    close_mcp,
    load_mcp_servers,
    parse_mcp_config,
)

__all__ = [
    "MCPClient",
    "MCPError",
    "MCPReport",
    "MCPServerConfig",
    "close_mcp",
    "load_mcp_servers",
    "parse_mcp_config",
]
