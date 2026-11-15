"""B1 — Tool registry: the formal tool contract.

Replaces the provisional ``tools_min`` (Fase A). A Tool declares:

- ``name`` / ``description`` / ``input_schema`` — what the model sees.
- ``permission`` — auto | ask | deny (policy enforcement arrives in B4; here
  the registry already HONOURS the flag: ``deny`` never runs, ``ask`` without
  an approver degrades to an honest error, ``auto`` runs).
- ``sandboxable`` — whether B3 (bwrap) may jail its execution.
- ``run`` — async callable(dict) -> str. Errors are RETURNED as "ERROR: ..."
  strings; unexpected exceptions are caught and converted (the loop never
  crashes on a tool bug — Fase A invariant).

Validation ladder (jsonschema BEFORE execution):
1. args parse (the loop already does JSON parsing; registry re-checks type),
2. schema validation → honest ERROR ToolResult so the model self-corrects,
3. permission gate,
4. run + truncation at the spout (M1).

Footprint rule (hermes AGENTS.md ladder): prefer extending an existing tool
over adding a new core tool.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import jsonschema
from jsonschema.exceptions import SchemaError

from tlamati.core.messages import ToolResult
from tlamati.providers.base import ToolSpec

MAX_OUTPUT_CHARS = 50_000  # M1: truncate at the spout, honest marker


class Permission(StrEnum):
    """Policy ladder (GUIA §B4). B1 only honours the flag; B4 wires config."""

    AUTO = "auto"  # runs without asking
    ASK = "ask"  # needs explicit approval (TUI prompt / --approve flag)
    DENY = "deny"  # never runs


# B4 will supply the real approver (TUI/headless policy). Signature:
# (tool_name, args) -> bool. Kept async so a TUI prompt doesn't block the loop.
Approver = Callable[[str, dict[str, Any]], Awaitable[bool]]


@dataclass(frozen=True)
class Tool:
    """The formal tool contract (GUIA §B1)."""

    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[[dict[str, Any]], Awaitable[str]]
    permission: Permission = Permission.AUTO
    sandboxable: bool = False

    def as_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, input_schema=self.input_schema
        )


def truncate(text: str) -> tuple[str, bool]:
    """M1 spout truncation with an honest marker (shared with B2 tools)."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n... [truncated]", True


def validate_schema(schema: dict[str, Any], args: dict[str, Any]) -> str | None:
    """Return None if args satisfy schema, else an honest error string.

    A malformed SCHEMA is a harness bug (not the model's) — surfaced loudly so
    tests catch it, but still returned as a string, never raised into the loop.
    """
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
    except SchemaError as e:
        return f"ERROR: tool schema is invalid (harness bug): {e.message}"
    errors = sorted(validator.iter_errors(args), key=lambda e: list(e.path))
    if not errors:
        return None
    details = "; ".join(
        f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors[:3]
    )
    return f"ERROR: invalid arguments — {details}"


class Registry:
    """Name → Tool lookup + guarded execution.

    Duplicate names are a programming error (fail fast at register, not at
    dispatch): two tools claiming one name would corrupt every audit trail.
    """

    def __init__(self, tools: list[Tool] | None = None, approver: Approver | None = None):
        self._tools: dict[str, Tool] = {}
        self.approver = approver
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool registration: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def specs(self) -> list[ToolSpec]:
        """Wire specs for the provider call (stable order = stable prefix)."""
        return [t.as_spec() for t in self._tools.values()]

    async def execute(self, name: str, args: dict[str, Any], tool_call_id: str) -> ToolResult:
        """Guarded execution: unknown → schema → permission → run.

        EVERY failure mode becomes an honest ToolResult(is_error=True); this
        method never raises (loop invariant from Fase A)."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"ERROR: unknown tool {name!r}",
                is_error=True,
            )

        if not isinstance(args, dict):
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"ERROR: arguments must be an object, got {type(args).__name__}",
                is_error=True,
            )

        # 1. jsonschema BEFORE execution (GUIA §B1).
        schema_error = validate_schema(tool.input_schema, args)
        if schema_error is not None:
            return ToolResult(tool_call_id=tool_call_id, content=schema_error, is_error=True)

        # 2. Permission gate. B4 replaces the approver; today ASK without an
        # approver degrades honestly (never silently runs, never yolo).
        if tool.permission is Permission.DENY:
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"ERROR: tool {name!r} is denied by policy",
                is_error=True,
            )
        if tool.permission is Permission.ASK:
            approved = False
            if self.approver is not None:
                try:
                    approved = await self.approver(name, args)
                except Exception as e:  # approver bugs must not kill the loop
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        content=f"ERROR: approval failed ({type(e).__name__}: {e})",
                        is_error=True,
                    )
            if not approved:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"ERROR: tool {name!r} requires approval and was not approved",
                    is_error=True,
                )

        # 3. Run — any exception becomes an honest error result.
        try:
            content = await tool.run(args)
            is_error = content.startswith("ERROR:")
        except Exception as e:
            content = f"ERROR: tool {name} raised {type(e).__name__}: {e}"
            is_error = True
        content, truncated = truncate(content)
        return ToolResult(
            tool_call_id=tool_call_id, content=content, is_error=is_error, truncated=truncated
        )
