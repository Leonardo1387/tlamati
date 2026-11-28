"""T1 — Detector de cuasi-stall (HANDOFF_DOGFOOD_27NOV §T1).

El bug real de dogfooding: el agente reintentaba la MISMA estrategia con
mutaciones menores (timeout 90→110, un flag extra, ruta cambiada) y el
detector EXACTO (stall_repeats, firma idéntica) nunca lo cazaba → gastaba
el presupuesto entero dando vueltas. El detector cuasi-repetitivo firma el
turno NORMALIZADO (dígitos→'#', whitespace→espacio) y compara similitud
contra una ventana deslizante.

Invariantes que estos tests protegen:
1. ≥warn_count cuasi-idénticas → evento quasi_stall_warning + aviso SOFT
   inyectado como user message (frontera de mensaje, NUNCA mid-stream).
2. El prefijo cacheable (system + user prompt + primera respuesta) queda
   byte-estable en TODA llamada al provider — caching is sacred.
3. Llamadas LEGÍTIMAS distintas → cero avisos (falsos positivos).
4. ≥ask_count → quasi_stall_ask; handler "parar"/sin handler = corte
   honesto stop_reason=stall; "seguir"/"redirigir" = limpia ventana y
   continúa (nunca corte duro por cuasi-similitud).
5. similarity=0 → detector inactivo, la ventana no se llena (costo cero).

Zero network: provider fake con turnos de tool mutados.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.core.loop import QuasiStallConfig, run_loop
from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.providers.base import ToolSpec
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry


class QuasiLoopProvider:
    """Emite N turnos de read_file con MUTACIONES MENORES (el patrón del
    bucle real: mismo comando, timeout/flag/ruta variando), luego end_turn.

    variant_fn(turn_index) -> dict de args: permite tests de llamadas
    legítimas distintas (sin cuasi-repetición)."""

    model = "quasi-fake"

    def __init__(self, tool_turns: int, variant_fn: Any = None) -> None:
        self.turns_left = tool_turns
        self.calls: list[list[Message]] = []
        self._variant_fn = variant_fn or self._default_variant

    @staticmethod
    def _default_variant(i: int) -> dict[str, Any]:
        # Mutación menor típica: timeout creciente + flag de reintento.
        return {"path": "a.txt", "timeout": 90 + i * 20, "_intento": i}

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        self.calls.append(list(messages))
        if self.turns_left > 0:
            self.turns_left -= 1
            tid = f"c{len(self.calls)}"
            yield ToolCallStart(id=tid, name="read_file")
            yield ToolCallArgsDelta(id=tid, args_json=json.dumps(self._variant_fn(len(self.calls))))
            yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))
        else:
            yield TextDelta(text="TERMINADO")
            yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text("contenido de prueba\n" * 10)
    return tmp_path


def _registry(workdir: Path) -> Registry:
    return Registry(make_tools(workdir))


# Umbrales bajos para tests rápidos (los defaults de producción son 5/8).
FAST = QuasiStallConfig(similarity=0.85, window=15, warn_count=3, ask_count=5)


class TestWarning:
    async def test_mutaciones_menores_disparan_aviso_soft(self, workdir: Path) -> None:
        p = QuasiLoopProvider(tool_turns=6)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=20,
            stall_repeats=0,  # aislar T1 del detector exacto
            quasi_stall=FAST,
            on_event=lambda k, d: events.append((k, d)),
        )
        warnings = [d for k, d in events if k == "quasi_stall_warning"]
        assert warnings, "6 llamadas cuasi-idénticas no dispararon ningún aviso"
        assert warnings[0]["matches"] >= FAST.warn_count
        # El aviso SOFT entró como user message en la history final.
        avisos = [
            m
            for m in result.history
            if m.role == "user" and m.content.startswith("[AVISO DE ESTANCAMIENTO")
        ]
        assert avisos, "el aviso SOFT no se inyectó como user message"
        # El modelo lo vio (aparece en alguna llamada posterior al provider).
        assert any(
            m.content.startswith("[AVISO DE ESTANCAMIENTO") for call in p.calls for m in call
        )

    async def test_llamadas_legitimas_sin_falsos_positivos(self, workdir: Path) -> None:
        # 4 llamadas LEGÍTIMAS distintas (distintos archivos/args de verdad).
        def legit(i: int) -> dict[str, Any]:
            distintos = [
                {"path": "a.txt", "offset": 1},
                {"path": "a.txt", "limit": 500},
                {"path": "a.txt", "offset": 20, "limit": 10},
                {"path": "a.txt"},
            ]
            return distintos[(i - 1) % len(distintos)]

        p = QuasiLoopProvider(tool_turns=4, variant_fn=legit)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="explora a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=20,
            stall_repeats=0,
            quasi_stall=FAST,
            on_event=lambda k, d: events.append((k, d)),
        )
        assert result.stop_reason == "end_turn"
        assert not [e for e in events if e[0].startswith("quasi_stall")], (
            "llamadas legítimas distintas dispararon el detector (falso positivo)"
        )

    async def test_aviso_no_rompe_prefijo_cacheable(self, workdir: Path) -> None:
        """REGLA DE ORO: el aviso entra al FINAL del turno como user message;
        el prefijo (system + user prompt + primera respuesta assistant) es
        byte-estable en TODA llamada (patrón de test_compaction.py:279)."""
        p = QuasiLoopProvider(tool_turns=6)
        await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=20,
            stall_repeats=0,
            quasi_stall=FAST,
        )

        def wire(m: Message) -> dict[str, Any]:
            d = m.as_dict()
            d.pop("id")
            return d

        first_full = next(c for c in p.calls if len(c) >= 3)
        for call in p.calls:
            assert wire(call[0]) == wire(first_full[0])  # system
            assert wire(call[1]) == wire(first_full[1])  # user prompt
            if len(call) >= 3:
                assert wire(call[2]) == wire(first_full[2])  # primera assistant


class TestAsk:
    async def test_handler_parar_corta_con_stall(self, workdir: Path) -> None:
        p = QuasiLoopProvider(tool_turns=20)
        decisions: list[int] = []

        async def ask(matches: int) -> str:
            decisions.append(matches)
            return "parar"

        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=30,
            stall_repeats=0,
            quasi_stall=FAST,
            quasi_ask=ask,
            on_event=lambda k, d: events.append((k, d)),
        )
        assert result.stop_reason == "stall"
        assert decisions and decisions[0] >= FAST.ask_count
        assert result.error and "el usuario decidió parar" in result.error
        assert [e for e in events if e[0] == "quasi_stall_stop"]

    async def test_handler_seguir_limpia_ventana_y_continua(self, workdir: Path) -> None:
        # 20 turnos: el primer ask llega ~en el 5; "seguir" limpia la ventana
        # y el contador tarda otros ~5 cuasi-iguales en volver al ask.
        p = QuasiLoopProvider(tool_turns=20)
        asked = 0

        async def ask(matches: int) -> str:
            nonlocal asked
            asked += 1
            return "seguir" if asked == 1 else "parar"

        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=30,
            stall_repeats=0,
            quasi_stall=FAST,
            quasi_ask=ask,
        )
        # "seguir" NO corta: el loop continuó hasta el segundo ask ("parar").
        assert asked == 2
        assert result.stop_reason == "stall"
        notas = [
            m for m in result.history if m.role == "user" and "[DECISIÓN DEL USUARIO]" in m.content
        ]
        assert notas, "la decisión 'seguir' no inyectó su nota como user message"

    async def test_handler_redirigir_inyecta_redireccion(self, workdir: Path) -> None:
        p = QuasiLoopProvider(tool_turns=20)

        async def ask(matches: int) -> str:
            return "redirigir"

        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=30,
            stall_repeats=0,
            quasi_stall=FAST,
            quasi_ask=ask,
        )
        # "redirigir" limpia la ventana y sigue; con 20 turnos cuasi-idénticos
        # vuelve a topar el ask (segunda vez) y otra vez redirige — el loop
        # termina por max_turns, NUNCA por corte duro cuasi.
        assert result.stop_reason in ("max_turns", "end_turn")
        assert any(
            m.role == "user" and "[REDIRECCIÓN DEL USUARIO]" in m.content for m in result.history
        )

    async def test_headless_sin_handler_degrada_a_stall(self, workdir: Path) -> None:
        """Sin quasi_ask (headless) el umbral de ASK = corte honesto, no cuelga."""
        p = QuasiLoopProvider(tool_turns=20)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=30,
            stall_repeats=0,
            quasi_stall=FAST,  # quasi_ask=None
            on_event=lambda k, d: events.append((k, d)),
        )
        assert result.stop_reason == "stall"
        assert result.error and "headless" in result.error
        assert [e for e in events if e[0] == "quasi_stall_ask"]
        assert [e for e in events if e[0] == "quasi_stall_stop"]


class TestDisabled:
    async def test_similarity_cero_desactiva_todo(self, workdir: Path) -> None:
        off = QuasiStallConfig(similarity=0.0)
        assert not off.enabled
        p = QuasiLoopProvider(tool_turns=8)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=20,
            stall_repeats=0,
            quasi_stall=off,
            on_event=lambda k, d: events.append((k, d)),
        )
        assert result.stop_reason == "end_turn"
        assert not [e for e in events if e[0].startswith("quasi_stall")]

    async def test_none_desactiva_como_antes(self, workdir: Path) -> None:
        p = QuasiLoopProvider(tool_turns=4)
        events: list[tuple[str, dict[str, Any]]] = []
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=20,
            stall_repeats=0,
            quasi_stall=None,
            on_event=lambda k, d: events.append((k, d)),
        )
        assert result.stop_reason == "end_turn"
        assert not [e for e in events if e[0].startswith("quasi_stall")]


class TestResolveQuasiStall:
    """cli.resolve_quasi_stall: config stall.* → QuasiStallConfig|None."""

    def test_defaults_sin_config(self) -> None:
        from tlamati.cli import resolve_quasi_stall

        qsc = resolve_quasi_stall({})
        assert qsc is not None
        assert (qsc.similarity, qsc.window, qsc.warn_count, qsc.ask_count) == (0.85, 15, 5, 8)

    def test_keys_de_config_sobreescriben(self) -> None:
        from tlamati.cli import resolve_quasi_stall

        qsc = resolve_quasi_stall(
            {
                "stall": {
                    "quasi_similarity": 0.9,
                    "quasi_window": 20,
                    "quasi_warn_count": 4,
                    "quasi_ask_count": 7,
                }
            }
        )
        assert qsc is not None
        assert (qsc.similarity, qsc.window, qsc.warn_count, qsc.ask_count) == (0.9, 20, 4, 7)

    def test_similarity_cero_desactiva(self) -> None:
        from tlamati.cli import resolve_quasi_stall

        assert resolve_quasi_stall({"stall": {"quasi_similarity": 0}}) is None

    def test_basura_degrada_a_defaults(self) -> None:
        from tlamati.cli import resolve_quasi_stall

        qsc = resolve_quasi_stall({"stall": {"quasi_similarity": "no-soy-numero"}})
        assert qsc is not None and qsc.similarity == 0.85
        # bloque stall que no es dict → no explota
        assert resolve_quasi_stall({"stall": "basura"}) is not None


class TestExactStallOrthogonal:
    async def test_detector_exacto_sigue_operando_independiente(self, workdir: Path) -> None:
        """Args IDÉNTICOS consecutivos: el corte duro exacto (stall_repeats)
        dispara ANTES que nada cuasi (decisión del fundador: nunca mezclar)."""
        p = QuasiLoopProvider(tool_turns=10, variant_fn=lambda i: {"path": "a.txt"})
        result = await run_loop(
            p,
            system="s",
            user_prompt="lee a.txt",
            tools=_registry(workdir),
            budget=Budget(50_000),
            max_turns=20,
            stall_repeats=3,  # detector exacto activo
            quasi_stall=FAST,
        )
        assert result.stop_reason == "stall"
        assert result.error and "bucle detectado" in result.error
