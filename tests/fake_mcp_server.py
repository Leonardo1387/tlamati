"""FakeMCPServer (D3) — servidor MCP de juguete que habla JSON-RPC 2.0 real
por stdio. NO es un mock en memoria: es un PROCESO de verdad, así los tests
cubren subprocess, pipes, handshake, timeouts y cierre.

Uso: python3 fake_mcp_server.py <modo>

Modos:
- ok              : handshake + 2 tools (echo, add) + call ok
- bad_handshake   : responde initialize con error JSON-RPC
- garbage_init    : responde basura no-JSON al initialize
- empty_tools     : handshake ok, tools/list devuelve lista vacía
- error_on_call   : call devuelve isError=true
- hang_on_call    : call NUNCA responde (timeout del cliente)
- hang_on_init    : no responde al initialize (timeout del handshake)
- die_immediately : exit 1 sin escribir nada (servidor que no arranca)
"""

import json
import sys
import time

MODE = sys.argv[1] if len(sys.argv) > 1 else "ok"

TOOLS = [
    {
        "name": "echo",
        "description": "Devuelve el texto recibido",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "add",
        "description": "Suma dos números",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
]


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


if MODE == "die_immediately":
    sys.exit(1)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        if MODE == "hang_on_init":
            time.sleep(3600)
        elif MODE == "bad_handshake":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32600, "message": "no te entiendo"},
                }
            )
        elif MODE == "garbage_init":
            sys.stdout.write("esto no es json\n")
            sys.stdout.flush()
        else:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake-mcp", "version": "0.1"},
                    },
                }
            )
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        tools = [] if MODE == "empty_tools" else TOOLS
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": tools}})
    elif method == "tools/call":
        if MODE == "hang_on_call":
            time.sleep(3600)
        elif MODE == "error_on_call":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "content": [{"type": "text", "text": "el servidor dice: fallé"}],
                        "isError": True,
                    },
                }
            )
        else:
            args = msg.get("params", {}).get("arguments", {})
            name = msg.get("params", {}).get("name")
            if name == "echo":
                text = f"eco remoto: {args.get('text', '')}"
            elif name == "add":
                text = str(args.get("a", 0) + args.get("b", 0))
            else:
                text = f"tool desconocida: {name}"
            send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {"content": [{"type": "text", "text": text}]},
                }
            )
