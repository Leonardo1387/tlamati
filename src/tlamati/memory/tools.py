"""Memory tools (C2): `memory` (batch add/replace/remove) + `search_memory`.

Footprint rule respected: ONE new core tool (`memory`) with an operations
array — the exact shape the founder already knows from hermes. `search_memory`
is a simple substring scan over entries (memory is tiny by design — hard caps;
no embeddings, no index).

search_memory output is microcompact-whitelisted (GUIA C3/C2 destilada, donor:
CC keeps search_memory re-fetchable): its results can be cleared from context
because the tool can always re-read them from disk.

Permission: memory writes are `auto` — they only touch the local memory dir,
never egress (B4 policy: no untrusted, no escalation needed).
"""

from __future__ import annotations

import contextlib
from typing import Any

from tlamati.memory.store import MemoryError, MemoryStore
from tlamati.tools.registry import Tool

MEMORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target": {
            "type": "string",
            "enum": ["memory", "user"],
            "description": "'memory' = notas del proyecto/agente; 'user' = perfil del usuario",
        },
        "operations": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "replace", "remove"]},
                    "content": {
                        "type": "string",
                        "description": "texto de la entrada (add/replace)",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "subcadena ÚNICA que identifica la entrada (replace/remove)",
                    },
                },
                "required": ["action"],
            },
            "description": "cambios atómicos: se validan todos y se escribe una sola vez",
        },
    },
    "required": ["target", "operations"],
}

SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "subcadena a buscar (case-insensitive)"},
        "target": {
            "type": "string",
            "enum": ["memory", "user", "all"],
            "description": "dónde buscar (default: all)",
        },
    },
    "required": ["query"],
}


def make_memory_tools(store: MemoryStore) -> list[Tool]:
    async def memory_run(args: dict[str, Any]) -> str:
        target = str(args.get("target", ""))
        ops_raw = args.get("operations") or []
        operations = [
            {str(k): str(v) for k, v in op.items()} for op in ops_raw if isinstance(op, dict)
        ]
        try:
            stats = store.apply_batch(target, operations)
        except MemoryError as e:
            mf_hint = ""
            with contextlib.suppress(MemoryError):
                mf_hint = f" Estado actual: {store.load(target).stats.human()}."
            return f"ERROR: {e}.{mf_hint} El archivo NO fue modificado."
        return f"OK {target}: {stats.human()}."

    async def search_memory_run(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).lower()
        target = str(args.get("target", "all"))
        if not query:
            return "ERROR: query vacío"
        targets = ("memory", "user") if target == "all" else (target,)
        hits: list[str] = []
        for t in targets:
            try:
                mf = store.load(t)
            except MemoryError as e:
                return f"ERROR: {e}"
            for entry in mf.entries:
                if query in entry.lower():
                    hits.append(f"[{t}] {entry}")
        if not hits:
            return f"(sin coincidencias para {query!r})"
        return "\n---\n".join(hits[:20])

    return [
        Tool(
            name="memory",
            description=(
                "Guardar hechos durables (preferencias del usuario, decisiones, "
                "estado del proyecto) en MEMORY.md/USER.md con límites duros. "
                "Batch atómico: add/replace/remove en una sola llamada; si el "
                "archivo se llena, consolida (replace/remove) en el mismo batch."
            ),
            input_schema=MEMORY_SCHEMA,
            run=memory_run,
        ),
        Tool(
            name="search_memory",
            description=(
                "Buscar subcadena en la memoria durable (memory + user). "
                "Resultado re-obtenible: la compactación puede limpiarlo sin pérdida."
            ),
            input_schema=SEARCH_SCHEMA,
            run=search_memory_run,
        ),
    ]
