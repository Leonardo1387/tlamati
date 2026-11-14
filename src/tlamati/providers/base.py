"""Provider protocol + shared streaming plumbing.

Invariant (PRD §7 #2): EVERY provider call goes through an adapter that
normalizes to core.messages events and degrades with a TYPED error — weird
finish/stop reasons never get silently dropped.

Semantics donor: hermes-agent anthropic_adapter.py (MIT) — cache_control
breakpoints, tool schema normalization, orphan handling. No lines copied.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

import httpx

from tlamati.core.messages import Event, Message

ErrorKind = Literal["http", "stream", "refusal", "config", "unknown"]


class ProviderError(Exception):
    """Typed provider failure. ``raw`` preserves the provider's verbatim
    value so unknown stop/finish reasons are auditable, never dropped."""

    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind = "unknown",
        retryable: bool = False,
        status: int | None = None,
        raw: Any = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.status = status
        self.raw = raw


@dataclass(frozen=True)
class ToolSpec:
    """Tool declaration sent to the model. Provisional shape for Fase A;
    the formal Tool (registry, permission, sandbox_policy) lands in B1 and
    maps onto this."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """The narrow interface between core/loop.py and any backend.

    ``model`` is declared read-only (property) so frozen dataclass adapters
    satisfy it structurally."""

    @property
    def model(self) -> str: ...

    def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        """Stream one assistant turn as normalized events. The final event is
        always MessageEnd."""
        ...


async def iter_sse(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Yield parsed JSON payloads from an SSE response. Stops at ``[DONE]``.
    Malformed data lines raise ProviderError(kind="stream") — fail loud, the
    loop decides retry policy."""
    async for line in response.aiter_lines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            return
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError as e:
            raise ProviderError(f"malformed SSE payload: {payload[:200]!r}", kind="stream") from e
        if not isinstance(obj, dict):
            raise ProviderError(f"SSE payload is not an object: {type(obj)}", kind="stream")
        yield obj


async def post_stream(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> httpx.Response:
    """Open the streaming POST, mapping HTTP failures to ProviderError.
    429/5xx are retryable; 4xx are not (donor semantics)."""
    try:
        response = await client.send(
            client.build_request("POST", url, headers=headers, json=payload), stream=True
        )
    except httpx.TransportError as e:
        raise ProviderError(f"transport error: {e}", kind="http", retryable=True) from e
    if response.status_code != 200:
        await response.aread()
        body = response.text[:500]
        raise ProviderError(
            f"provider HTTP {response.status_code}: {body}",
            kind="http",
            retryable=response.status_code == 429 or response.status_code >= 500,
            status=response.status_code,
        )
    return response


def tools_to_openai(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema or {"type": "object", "properties": {}},
            },
        }
        for t in tools
    ]


def tools_to_anthropic(
    tools: Sequence[ToolSpec], *, cache_last: bool = True
) -> list[dict[str, Any]]:
    """Anthropic tool shape = {name, description, input_schema}. The LAST tool
    carries the cache_control breakpoint (tools+system are the cacheable
    prefix; donor pattern)."""
    out: list[dict[str, Any]] = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema or {"type": "object", "properties": {}},
        }
        for t in tools
    ]
    if out and cache_last:
        out[-1]["cache_control"] = {"type": "ephemeral"}
    return out
