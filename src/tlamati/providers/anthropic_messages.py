"""Anthropic Messages API adapter.

Semantics donor: hermes-agent anthropic_adapter.py (MIT) — cache_control
breakpoints on the cacheable prefix (system + tools), tool_use/tool_result
block shapes, consecutive-role merging, orphan tool-block stripping. No lines
copied; re-derived from documented semantics.

Cache invariant ("prompt caching is sacred", PRD §7 #1):
- Breakpoint 1: LAST tool in the tools array (tools_to_anthropic in base.py).
- Breakpoint 2: LAST system content block (built here).
- History is NOT breakpointed in Fase A (short sessions); compaction (A6)
  will own the suffix-side edits and may add one moving breakpoint at the
  last stable assistant turn.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.providers.base import (
    ToolSpec,
    iter_sse,
    post_stream,
    tools_to_anthropic,
)

# Normalized stop vocabulary (donor semantics: unknown → typed error, raw kept).
_STOP_MAP: dict[str, str] = {
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
    "pause_turn": "end_turn",
}


def _merge_consecutive_roles(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic rejects two same-role messages in a row. Merge by joining
    content blocks (donor pattern)."""
    merged: list[dict[str, Any]] = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            prev_c = merged[-1]["content"]
            cur_c = m["content"]
            prev_blocks = prev_c if isinstance(prev_c, list) else [{"type": "text", "text": prev_c}]
            cur_blocks = cur_c if isinstance(cur_c, list) else [{"type": "text", "text": cur_c}]
            merged[-1]["content"] = [*prev_blocks, *cur_blocks]
        else:
            merged.append(m)
    return merged


@dataclass(frozen=True)
class AnthropicMessages:
    """Provider for the Anthropic Messages API (direct, or OpenRouter's
    anthropic-compatible surface via base_url override)."""

    model: str
    api_key: str = ""
    base_url: str = "https://api.anthropic.com"
    max_tokens: int = 8192
    timeout_s: float = 180.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    transport: httpx.AsyncBaseTransport | None = None  # test injection (MockTransport)

    def _url(self) -> str:
        return self.base_url.rstrip("/") + "/v1/messages"

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            **self.extra_headers,
        }
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    def _build_system(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        """All system messages → one content-block list; the LAST block gets
        the cache breakpoint (keeps the prefix byte-stable and cacheable)."""
        blocks: list[dict[str, Any]] = [
            {"type": "text", "text": m.content} for m in messages if m.role == "system"
        ]
        if blocks:
            blocks[-1]["cache_control"] = {"type": "ephemeral"}
        return blocks

    def _build_history(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role in ("user", "assistant"):
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments or json.loads(tc.raw_arguments or "{}"),
                        }
                    )
                history.append({"role": m.role, "content": blocks or m.content})
            elif m.role == "tool":
                tr = m.tool_result
                assert tr is not None  # Message.__post_init__ guarantees
                block: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": tr.tool_call_id,
                    "content": tr.content,
                }
                if tr.is_error:
                    block["is_error"] = True
                history.append({"role": "user", "content": [block]})
        return _merge_consecutive_roles(self._strip_orphans(history))

    @staticmethod
    def _strip_orphans(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop tool_result blocks whose tool_use never made it into history
        (donor pattern: orphan tool blocks make Anthropic 400)."""
        seen_ids: set[str] = set()
        for m in history:
            content = m.get("content")
            if isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_use":
                        seen_ids.add(b.get("id", ""))
        out: list[dict[str, Any]] = []
        for m in history:
            content = m.get("content")
            if isinstance(content, list):
                kept = [
                    b
                    for b in content
                    if not (b.get("type") == "tool_result" and b.get("tool_use_id") not in seen_ids)
                ]
                if not kept:
                    continue  # whole message was orphan results
                m = {**m, "content": kept}
            out.append(m)
        return out

    def _payload(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self._build_system(messages),
            "messages": self._build_history(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools_to_anthropic(tools)
        return payload

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        timeout = httpx.Timeout(self.timeout_s, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            response = await post_stream(
                client, self._url(), self._headers(), self._payload(messages, tools)
            )
            try:
                async for ev in self._consume(response):
                    yield ev
            finally:
                await response.aclose()

    async def _consume(self, response: httpx.Response) -> AsyncIterator[Event]:
        usage = Usage()
        stop_reason = "end_turn"
        raw_stop: Any = None
        # Anthropic streams: message_start (usage), content_block_start
        # (tool_use id/name), content_block_delta (text_delta / input_json_delta),
        # message_delta (stop_reason + output usage).
        cur_tool_id = ""
        async for chunk in iter_sse(response):
            etype = chunk.get("type", "")
            if etype == "error":
                err = chunk.get("error") or {}
                yield MessageEnd(
                    stop_reason="error",
                    usage=usage,
                    error=f"{err.get('type', 'error')}: {err.get('message', '')}",
                )
                return
            if etype == "message_start":
                u = (chunk.get("message") or {}).get("usage") or {}
                usage = self._merge_usage(usage, u)
            elif etype == "content_block_start":
                block = chunk.get("content_block") or {}
                if block.get("type") == "tool_use":
                    cur_tool_id = block.get("id", "")
                    yield ToolCallStart(id=cur_tool_id, name=block.get("name", ""))
            elif etype == "content_block_delta":
                delta = chunk.get("delta") or {}
                dtype = delta.get("type")
                if dtype == "text_delta" and delta.get("text"):
                    yield TextDelta(text=delta["text"])
                elif dtype == "input_json_delta" and delta.get("partial_json"):
                    yield ToolCallArgsDelta(id=cur_tool_id, args_json=delta["partial_json"])
            elif etype == "message_delta":
                d = chunk.get("delta") or {}
                if d.get("stop_reason"):
                    raw_stop = d["stop_reason"]
                    mapped = _STOP_MAP.get(raw_stop)
                    stop_reason = mapped if mapped else "error"
                if chunk.get("usage"):
                    usage = self._merge_usage(usage, chunk["usage"])

        if stop_reason == "error":
            yield MessageEnd(
                stop_reason="error",
                usage=usage,
                error=f"unrecognized stop_reason {raw_stop!r}",
            )
            return
        yield MessageEnd(stop_reason=stop_reason, usage=usage)  # type: ignore[arg-type]

    @staticmethod
    def _merge_usage(cur: Usage, u: dict[str, Any]) -> Usage:
        """Anthropic reports input usage on message_start and output usage on
        message_delta; cache fields only appear when a breakpoint hit."""
        cost = cur.cost_usd
        merged = Usage(
            input_tokens=int(u.get("input_tokens", cur.input_tokens) or 0)
            if "input_tokens" in u
            else cur.input_tokens,
            output_tokens=int(u.get("output_tokens", cur.output_tokens) or 0)
            if "output_tokens" in u
            else cur.output_tokens,
            cache_read_tokens=int(u.get("cache_read_input_tokens", cur.cache_read_tokens) or 0),
            cache_write_tokens=int(
                u.get("cache_creation_input_tokens", cur.cache_write_tokens) or 0
            ),
            cost_usd=cost,
        )
        return merged
