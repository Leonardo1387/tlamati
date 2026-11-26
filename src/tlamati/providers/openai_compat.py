"""OpenAI-compatible chat/completions adapter.

Covers OpenRouter, Ollama, vLLM — anything exposing
POST {base_url}/chat/completions with SSE streaming. Config = base_url +
api_key + model (PRD §3 #2: the model is a plug-in).

Format-fallback duty (anti-pattern "formats one agent emits another won't
parse"): tool-call argument chunks are accumulated per-index, parsed once at
the end; a JSON parse failure degrades to MessageEnd(stop_reason="error")
with the raw string preserved — never a silent drop.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from tlamati.core.images import ImageBlock
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
    ProviderError,
    ToolSpec,
    iter_sse,
    post_stream,
    tools_to_openai,
)

# Normalized stop vocabulary. Anything unknown → "error" with raw preserved.
_FINISH_MAP: dict[str | None, str] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "length": "max_tokens",
    "content_filter": "refusal",
}


def _is_anthropic(model: str) -> bool:
    """Anthropic models do NOT auto-cache: the prefix is only cached when the
    request carries explicit cache_control markers (verified live against
    OpenRouter chat/completions 2026-11-20: plain repeat = cached 0; with
    markers = 99% hit, 19x cheaper). Other families (OpenAI/Qwen/DeepSeek)
    auto-cache, so sending them markers would be noise."""
    return model.startswith(("anthropic/", "claude-"))


def _openai_content_blocks(text: str, images: Sequence[ImageBlock]) -> list[dict[str, Any]]:
    """Vision v2.1: text + images → OpenAI-style content block list.

    Images travel as data-URLs (the wire form every OpenAI-compatible vision
    gateway accepts, OpenRouter included). The text marker goes FIRST so a
    gateway sin visión que degrade a texto aún muestra el registro honesto
    de qué imagen era.
    """
    blocks: list[dict[str, Any]] = []
    if text:
        blocks.append({"type": "text", "text": text})
    for im in images:
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{im.media_type};base64,{im.data}"},
            }
        )
    return blocks


@dataclass(frozen=True)
class OpenAICompat:
    """Provider for OpenAI-compatible endpoints."""

    model: str
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: str = ""
    max_tokens: int = 8192
    temperature: float | None = None
    timeout_s: float = 120.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    transport: httpx.AsyncBaseTransport | None = None  # test injection (MockTransport)

    def _url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    async def list_models(self) -> list[str]:
        """Model ids available at this endpoint (GET {base_url}/models).

        Fail-loud: any transport/HTTP/shape problem raises ProviderError —
        the caller (ModelRouter / TUI) decides the fallback to config.
        Never returns a partial or invented list.
        """
        url = self.base_url.rstrip("/") + "/models"
        timeout = httpx.Timeout(self.timeout_s)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            try:
                resp = await client.get(url, headers=self._headers())
            except httpx.TransportError as e:
                raise ProviderError(
                    f"list_models transport error: {e}", kind="http", retryable=True
                ) from e
            if resp.status_code != 200:
                raise ProviderError(
                    f"list_models HTTP {resp.status_code}: {resp.text[:200]}",
                    kind="http",
                    status=resp.status_code,
                    retryable=resp.status_code == 429 or resp.status_code >= 500,
                )
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderError(f"list_models malformed JSON: {e}", kind="stream") from e
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ProviderError(
                "list_models: unexpected payload shape (no 'data' list)",
                kind="stream",
                raw=data if isinstance(data, dict) else None,
            )
        ids = [str(m["id"]) for m in items if isinstance(m, dict) and m.get("id")]
        return sorted(set(ids))

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _payload(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> dict[str, Any]:
        converted = [self._convert_message(m) for m in messages]
        if _is_anthropic(self.model):
            self._mark_anthropic_cache(converted)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": converted,
            "stream": True,
            "max_tokens": self.max_tokens,
            "stream_options": {"include_usage": True},
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if tools:
            payload["tools"] = tools_to_openai(tools)
        return payload

    @staticmethod
    def _mark_anthropic_cache(converted: list[dict[str, Any]]) -> None:
        """Explicit cache breakpoints for Anthropic models (they never
        auto-cache). Two of the four allowed markers, mirroring
        anthropic_messages.py semantics + the verified-live rolling pattern:
        (1) LAST system block = stable prefix; (2) LAST tool result = rolling
        breakpoint so the growing history stays cached turn over turn
        (probe 20-nov: 99.8% hit, 19x cheaper than plain)."""
        last_system = next((m for m in reversed(converted) if m["role"] == "system"), None)
        if last_system is not None and isinstance(last_system["content"], str):
            last_system["content"] = [
                {
                    "type": "text",
                    "text": last_system["content"],
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        last_tool = next((m for m in reversed(converted) if m["role"] == "tool"), None)
        if last_tool is not None:
            c = last_tool["content"]
            if isinstance(c, str):
                last_tool["content"] = [
                    {"type": "text", "text": c, "cache_control": {"type": "ephemeral"}}
                ]
            elif isinstance(c, list) and c:
                # Vision v2.1: tool result con imágenes = lista de bloques; el
                # breakpoint rolling va al ÚLTIMO bloque (el de visión).
                c[-1] = {**c[-1], "cache_control": {"type": "ephemeral"}}

    @staticmethod
    def _convert_message(m: Message) -> dict[str, Any]:
        if m.role == "system":
            return {"role": "system", "content": m.content}
        if m.role == "user":
            if m.images:
                return {
                    "role": "user",
                    "content": _openai_content_blocks(m.content, m.images),
                }
            return {"role": "user", "content": m.content}
        if m.role == "assistant":
            out: dict[str, Any] = {"role": "assistant", "content": m.content or None}
            if m.tool_calls:
                out["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.raw_arguments or json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            return out
        if m.role == "tool":
            tr = m.tool_result
            assert tr is not None  # Message.__post_init__ guarantees
            content: Any = tr.content
            if tr.images:
                # OpenAI-style: el tool message acepta lista de bloques
                # text + image_url (data-URL) en gateways con visión.
                content = _openai_content_blocks(tr.content, tr.images)
            return {"role": "tool", "tool_call_id": tr.tool_call_id, "content": content}
        raise ProviderError(f"unknown role {m.role!r}", kind="config")

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
        finish_raw: Any = None
        # Per-index accumulation: OpenAI streams tool args as fragments keyed
        # by choice delta index; id/name arrive on the first fragment.
        pending: dict[int, dict[str, str]] = {}
        async for chunk in iter_sse(response):
            # Provider-level error object (some gateways do HTTP 200 + error body)
            if isinstance(chunk.get("error"), dict):
                err = chunk["error"]
                yield MessageEnd(
                    stop_reason="error",
                    usage=usage,
                    error=f"{err.get('message', err)}",
                )
                return
            if chunk.get("usage"):
                u = chunk["usage"]
                # Bug 4 autopsia dogfooding #2: turn_costs.cost_usd quedaba NULL.
                # Causa: OpenRouter SÍ reporta el costo real en el chunk final
                # de usage (campo "cost", presente con stream_options
                # include_usage), pero este parser lo ignoraba. Se usa el valor
                # reportado cuando existe; si el gateway no lo trae, cost_usd
                # sigue siendo None honesto (nunca inventado).
                raw_cost = u.get("cost")
                cost = float(raw_cost) if isinstance(raw_cost, (int, float)) else None
                usage = Usage(
                    input_tokens=int(u.get("prompt_tokens", 0) or 0),
                    output_tokens=int(u.get("completion_tokens", 0) or 0),
                    cache_read_tokens=int(
                        (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
                    ),
                    cost_usd=cost,
                )
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                text = delta.get("content")
                if text:
                    yield TextDelta(text=text)
                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index", 0))
                    slot = pending.setdefault(idx, {"id": "", "name": "", "args": ""})
                    fn = tc.get("function") or {}
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                        slot["name"] = fn.get("name", "")
                        yield ToolCallStart(id=slot["id"], name=slot["name"])
                    if fn.get("name") and slot["name"] == "":
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]
                        yield ToolCallArgsDelta(id=slot["id"], args_json=fn["arguments"])
                fr = choice.get("finish_reason")
                if fr is not None:
                    finish_raw = fr
                    stop_reason = _FINISH_MAP.get(fr, "error")

        if stop_reason == "error":
            yield MessageEnd(
                stop_reason="error",
                usage=usage,
                error=f"unrecognized finish_reason {finish_raw!r}",
            )
            return
        if pending:
            # Validate accumulated JSON here so the loop gets typed errors, not
            # half-parsed garbage.
            for slot in pending.values():
                try:
                    json.loads(slot["args"] or "{}")
                except json.JSONDecodeError as e:
                    raw_args = slot["args"][:300]
                    yield MessageEnd(
                        stop_reason="error",
                        usage=usage,
                        error=f"tool-call arguments not valid JSON: {e}; raw={raw_args!r}",
                    )
                    return
            stop_reason = "tool_use"
        yield MessageEnd(stop_reason=stop_reason, usage=usage)  # type: ignore[arg-type]
