"""F1 fase A — tests de list_models (providers) y ModelRouter (swap en vivo).

Zero network: httpx.MockTransport en todos los casos (patrón test_providers.py).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from tlamati.core.messages import Event, MessageEnd, Usage
from tlamati.core.model_router import ModelRouter
from tlamati.providers.anthropic_messages import AnthropicMessages
from tlamati.providers.base import ProviderError
from tlamati.providers.openai_compat import OpenAICompat


def _mock_json(payload: dict[str, Any], status: int = 200, seen: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen["url"] = str(request.url)
            seen["headers"] = dict(request.headers)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


_MODELS = {
    "data": [
        {"id": "claude-opus-5-5"},
        {"id": "claude-sonnet-3-5"},
        {"id": "claude-haiku-4-5"},
        {"id": "claude-opus-5-5"},
    ]
}


# --------------------------------------------------------------------------
# OpenAICompat.list_models
# --------------------------------------------------------------------------


class TestOpenAICompatListModels:
    async def test_returns_sorted_deduped_ids(self) -> None:
        p = OpenAICompat(
            model="m",
            base_url="https://x.test/api/v1",
            api_key="sk-test-0000",
            transport=_mock_json(_MODELS),
        )
        ids = await p.list_models()
        assert ids == ["claude-haiku-4-5", "claude-opus-5-5", "claude-sonnet-3-5"]

    async def test_hits_models_endpoint_with_bearer(self) -> None:
        seen: dict[str, Any] = {}
        p = OpenAICompat(
            model="m",
            base_url="https://x.test/api/v1",
            api_key="sk-test-0000",
            transport=_mock_json(_MODELS, seen=seen),
        )
        await p.list_models()
        assert seen["url"] == "https://x.test/api/v1/models"
        assert seen["headers"]["authorization"] == "Bearer sk-test-0000"

    async def test_trailing_slash_normalized(self) -> None:
        seen: dict[str, Any] = {}
        p = OpenAICompat(
            model="m", base_url="https://x.test/api/v1/", transport=_mock_json(_MODELS, seen=seen)
        )
        await p.list_models()
        assert seen["url"] == "https://x.test/api/v1/models"

    async def test_http_error_raises_typed(self) -> None:
        p = OpenAICompat(
            model="m",
            base_url="https://x.test/api/v1",
            transport=_mock_json({"error": "boom"}, status=403),
        )
        with pytest.raises(ProviderError) as ei:
            await p.list_models()
        assert ei.value.kind == "http"
        assert ei.value.status == 403
        assert ei.value.retryable is False

    async def test_malformed_shape_raises(self) -> None:
        p = OpenAICompat(
            model="m", base_url="https://x.test/api/v1", transport=_mock_json({"nope": True})
        )
        with pytest.raises(ProviderError, match="shape"):
            await p.list_models()


# --------------------------------------------------------------------------
# AnthropicMessages.list_models
# --------------------------------------------------------------------------


class TestAnthropicListModels:
    async def test_native_host_uses_v1_models(self) -> None:
        seen: dict[str, Any] = {}
        p = AnthropicMessages(
            model="claude-opus-5-5",
            api_key="sk-ant-test-000",
            transport=_mock_json(_MODELS, seen=seen),
        )
        ids = await p.list_models()
        assert seen["url"] == "https://api.anthropic.com/v1/models"
        assert seen["headers"]["x-api-key"] == "sk-ant-test-000"
        assert "claude-opus-5-5" in ids

    async def test_openrouter_style_base_uses_models(self) -> None:
        seen: dict[str, Any] = {}
        p = AnthropicMessages(
            model="anthropic/claude",
            api_key="sk-or-test-000",
            base_url="https://openrouter.ai/api/v1",
            transport=_mock_json(_MODELS, seen=seen),
        )
        await p.list_models()
        assert seen["url"] == "https://openrouter.ai/api/v1/models"

    async def test_http_5xx_retryable(self) -> None:
        p = AnthropicMessages(model="m", transport=_mock_json({}, status=503))
        with pytest.raises(ProviderError) as ei:
            await p.list_models()
        assert ei.value.retryable is True


# --------------------------------------------------------------------------
# ModelRouter
# --------------------------------------------------------------------------


class _FakeProvider:
    def __init__(self, model: str, events: list[Event] | None = None) -> None:
        self.model = model
        self._events = events or [MessageEnd(stop_reason="end_turn", usage=Usage())]
        self.calls = 0

    async def stream(self, messages, tools=()) -> AsyncIterator[Event]:  # type: ignore[no-untyped-def]
        self.calls += 1
        for e in self._events:
            yield e


class TestModelRouter:
    def _router(self, **kw: Any) -> ModelRouter:
        ps = {m: _FakeProvider(m) for m in ("opus", "sonnet", "haiku")}
        return ModelRouter(providers=ps, active=kw.pop("active", "opus"), **kw)

    def test_model_property_tracks_active(self) -> None:
        r = self._router()
        assert r.model == "opus"
        r.set_model("haiku")
        assert r.model == "haiku"

    def test_set_model_unknown_raises_config(self) -> None:
        r = self._router()
        with pytest.raises(ProviderError) as ei:
            r.set_model("gpt-99")
        assert ei.value.kind == "config"
        assert r.model == "opus"  # no mutó

    def test_set_model_same_is_noop_no_hook(self) -> None:
        swaps: list[tuple[str, str]] = []
        r = self._router(on_swap=lambda ts, out, ins: swaps.append((out, ins)))
        r.set_model("opus")
        assert swaps == []

    def test_swap_fires_hook_with_out_and_in(self) -> None:
        swaps: list[tuple[str, str]] = []
        r = self._router(on_swap=lambda ts, out, ins: swaps.append((out, ins)))
        out = r.set_model("sonnet")
        assert out == "opus"
        assert swaps == [("opus", "sonnet")]

    def test_active_not_registered_fails_at_init(self) -> None:
        ps = {"opus": _FakeProvider("opus")}
        with pytest.raises(ProviderError, match="no registrado"):
            ModelRouter(providers=ps, active="ghost")

    async def test_stream_delegates_to_current_provider(self) -> None:
        r = self._router()
        evs = [e async for e in r.stream([])]
        assert evs and isinstance(evs[-1], MessageEnd)
        assert r.providers["opus"].calls == 1  # type: ignore[union-attr]
        r.set_model("sonnet")
        async for _ in r.stream([]):
            pass
        assert r.providers["sonnet"].calls == 1  # type: ignore[union-attr]
        assert r.providers["opus"].calls == 1  # type: ignore[union-attr]

    async def test_swap_between_turns_only_needs_boundary(self) -> None:
        # Invariante: un stream EN VUELTO termina con el modelo saliente
        # aunque se cambie el activo a mitad. El loop crea el stream y consume
        # su primer evento en el mismo paso del event loop; un swap entre
        # turnos solo afecta al SIGUIENTE stream.
        r = self._router()
        stream = r.stream([])
        it = stream.__aiter__()
        first = await it.__anext__()  # turno arrancado: provider ya capturado
        assert first is not None
        r.set_model("haiku")  # swap "a mitad" (no debería pasar; probamos)
        async for _ in stream:
            pass
        assert r.providers["opus"].calls == 1  # type: ignore[union-attr]
        assert r.providers["haiku"].calls == 0  # type: ignore[union-attr]

    def test_add_provider_extends_registry(self) -> None:
        r = self._router()
        r.add_provider(_FakeProvider("kimi"))
        r.set_model("kimi")
        assert r.model == "kimi"

    def test_add_provider_without_model_raises(self) -> None:
        r = self._router()

        class Bare: ...

        with pytest.raises(ProviderError, match="no enrutable"):
            r.add_provider(Bare())

    def test_cache_hint_hot_cold_unknown(self) -> None:
        r = self._router()
        assert r.cache_hint("sonnet") == "cold"  # nunca usado
        r.last_used_ts["sonnet"] = time.time() - 10
        assert r.cache_hint("sonnet") == "hot"
        r.last_used_ts["sonnet"] = time.time() - 3600
        assert r.cache_hint("sonnet") == "cold"
        assert r.cache_hint("sonnet", ttl_s=7200) == "hot"

    async def test_stream_marks_model_used_for_cache_hint(self) -> None:
        r = self._router()
        assert r.cache_hint("opus") == "cold"
        async for _ in r.stream([]):
            pass
        assert r.cache_hint("opus") == "hot"

    async def test_list_models_delegates_to_reference(self) -> None:
        class WithList(_FakeProvider):
            async def list_models(self) -> list[str]:
                return ["opus", "sonnet", "haiku"]

        ps = {m: WithList(m) for m in ("opus", "sonnet", "haiku")}
        r = ModelRouter(providers=ps, active="opus")
        # el router delega tal cual: NO re-ordena ni deduplica aquí
        # (la normalización le toca al caller/TUI)
        assert await r.list_models() == ["opus", "sonnet", "haiku"]

    async def test_list_models_fail_loud_when_unsupported(self) -> None:
        r = self._router()  # _FakeProvider no tiene list_models
        with pytest.raises(ProviderError, match="list_models"):
            await r.list_models()

    async def test_list_models_propagates_provider_error(self) -> None:
        class Boom(_FakeProvider):
            async def list_models(self) -> list[str]:
                raise ProviderError("HTTP 403", kind="http", status=403)

        ps = {"opus": Boom("opus")}
        r = ModelRouter(providers=ps, active="opus")
        with pytest.raises(ProviderError) as ei:
            await r.list_models()
        assert ei.value.status == 403
