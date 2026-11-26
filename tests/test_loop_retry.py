"""Tests del retry con backoff para errores transitorios del proveedor.

Fix 26-nov: rate limit de Alibaba vía OpenRouter mataba la corrida con
respuesta vacía (stop=error, in=0 out=0) porque el loop nunca consultaba
ProviderError.retryable ni detectaba errores transitorios en MessageEnd.

Cobertura:
  1. ProviderError(retryable=True) → reintenta y completa.
  2. ProviderError(retryable=False) → NO reintenta (falla inmediato).
  3. MessageEnd(error) con texto transitorio (rate limit) → reintenta.
  4. MessageEnd(error) determinista (finish_reason desconocido) → NO reintenta.
  5. Agotados los reintentos → devuelve el error honesto (stop_reason="error").
  6. El evento "retry" se emite con attempt/delay.
  7. _is_transient_error: patrones positivos y negativos.

Backoff parcheado a 0 para tests rápidos (asyncio.sleep mockeado).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.core import loop as loop_mod
from tlamati.core.loop import _is_transient_error, run_loop
from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    Usage,
)
from tlamati.providers.base import ProviderError, ToolSpec
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duerme 0 en el backoff — los tests no esperan 60s reales."""
    real_sleep = asyncio.sleep

    async def instant(delay: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(loop_mod.asyncio, "sleep", instant)


class ScriptedProvider:
    """Provider guionado: cada stream() ejecuta el siguiente paso de la lista.

    Un paso es:
      ("ok", texto)                 → turno normal con MessageEnd(end_turn)
      ("raise", ProviderError)      → lanza la excepción
      ("end_error", mensaje)        → MessageEnd(stop_reason="error", error=…)
    """

    model = "fake-retry"

    def __init__(self, script: list[tuple[Any, ...]]) -> None:
        self.script = list(script)
        self.stream_calls = 0

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.stream_calls += 1
        step = self.script.pop(0) if self.script else ("ok", "fin")
        kind = step[0]
        if kind == "raise":
            exc = step[1]
            assert isinstance(exc, BaseException)
            raise exc
        if kind == "end_error":
            yield MessageEnd(
                stop_reason="error",
                usage=Usage(),
                error=str(step[1]),
            )
            return
        yield TextDelta(text=str(step[1]))
        yield MessageEnd(
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=5),
        )


@pytest.fixture
def empty_registry(tmp_path: Path) -> Registry:
    return Registry(make_tools(tmp_path))


class TestRetryableProviderError:
    async def test_retryable_error_retries_and_succeeds(
        self, empty_registry: Registry
    ) -> None:
        p = ScriptedProvider(
            [
                ("raise", ProviderError("HTTP 429: rate limit", kind="http",
                                        retryable=True, status=429)),
                ("ok", "recuperado"),
            ]
        )
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
        )
        assert result.stop_reason == "end_turn"
        assert result.final_text == "recuperado"
        assert p.stream_calls == 2

    async def test_non_retryable_error_fails_immediately(
        self, empty_registry: Registry
    ) -> None:
        p = ScriptedProvider(
            [
                ("raise", ProviderError("HTTP 401: invalid key", kind="http",
                                        retryable=False, status=401)),
                ("ok", "no debería llegar"),
            ]
        )
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
        )
        assert result.stop_reason == "error"
        assert p.stream_calls == 1  # sin reintento en error determinista

    async def test_exhausted_retries_returns_error(
        self, empty_registry: Registry
    ) -> None:
        # 1 inicial + _MAX_PROVIDER_RETRIES reintentos, todos fallan
        steps: list[tuple[Any, ...]] = [
            ("raise", ProviderError("429 rate limit", kind="http", retryable=True))
            for _ in range(loop_mod._MAX_PROVIDER_RETRIES + 1)
        ]
        p = ScriptedProvider(steps)
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
        )
        assert result.stop_reason == "error"
        assert p.stream_calls == loop_mod._MAX_PROVIDER_RETRIES + 1


class TestTransientMessageEnd:
    async def test_rate_limit_message_end_retries(
        self, empty_registry: Registry
    ) -> None:
        p = ScriptedProvider(
            [
                ("end_error", "Upstream error from Alibaba: An error occurred "
                              "in model serving, error message is: [Rate limit "
                              "reached. Please slow down and retry.]"),
                ("ok", "segunda oportunidad"),
            ]
        )
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
        )
        assert result.stop_reason == "end_turn"
        assert result.final_text == "segunda oportunidad"
        assert p.stream_calls == 2

    async def test_deterministic_message_end_no_retry(
        self, empty_registry: Registry
    ) -> None:
        p = ScriptedProvider(
            [
                ("end_error", "unrecognized finish_reason 'weird_stop'"),
                ("ok", "no debería llegar"),
            ]
        )
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
        )
        assert result.stop_reason == "error"
        assert p.stream_calls == 1

    async def test_exhausted_transient_returns_partial_result(
        self, empty_registry: Registry
    ) -> None:
        steps: list[tuple[Any, ...]] = [
            ("end_error", "rate limit reached")
            for _ in range(loop_mod._MAX_PROVIDER_RETRIES + 1)
        ]
        p = ScriptedProvider(steps)
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
        )
        assert result.stop_reason == "error"
        assert "rate limit" in (result.error or "").lower()
        assert p.stream_calls == loop_mod._MAX_PROVIDER_RETRIES + 1


class TestRetryEvent:
    async def test_retry_event_emitted(self, empty_registry: Registry) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        p = ScriptedProvider(
            [
                ("raise", ProviderError("429", kind="http", retryable=True)),
                ("ok", "listo"),
            ]
        )
        result = await run_loop(
            p, system="s", user_prompt="hi", tools=empty_registry,
            budget=Budget(100_000), max_turns=5,
            on_event=lambda kind, data: events.append((kind, data)),
        )
        assert result.stop_reason == "end_turn"
        retries = [d for k, d in events if k == "retry"]
        assert len(retries) == 1
        assert retries[0]["attempt"] == 1
        assert retries[0]["delay_s"] > 0


class TestIsTransientError:
    @pytest.mark.parametrize(
        "msg",
        [
            "Upstream error from Alibaba: Rate limit reached. Please slow down.",
            "HTTP 429: too many requests",
            "This request would exceed your available credits given your "
            "current in-flight requests.",
            "provider HTTP 503: service unavailable",
            "model serving error, overloaded",
            "connection reset by peer",
            "request timed out",
        ],
    )
    def test_positive(self, msg: str) -> None:
        assert _is_transient_error(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            None,
            "",
            "unrecognized finish_reason 'weird'",
            "tool-call arguments not valid JSON: expecting value",
            "HTTP 401: invalid api key",
            "malformed SSE payload",
        ],
    )
    def test_negative(self, msg: str | None) -> None:
        assert _is_transient_error(msg) is False
