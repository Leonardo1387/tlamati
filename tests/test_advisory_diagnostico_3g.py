"""NIVEL 3g — advisory de diagnóstico en el system prompt (dogfood #6).

Origen: falso positivo OCR — el agente culpó al corpus cuando el stream
crudo de producción salía limpio (evidencia seq298 vs seq302 de la sesión
20261121-201254). El fix es prompt, no código: 1-2 líneas máximo porque
el prefijo es cache sagrada (STABILITY.md v0.1).
"""

from __future__ import annotations

from tlamati.cli import DEFAULT_SYSTEM


def test_advisory_parsing_presente() -> None:
    assert "el bug es de tu parsing" in DEFAULT_SYSTEM


def test_advisory_es_corto() -> None:
    """Restricción del handoff: 1-2 líneas máximo — verificamos que la
    añadidura total al prefijo es chica (<300 chars) para no inflar la cache."""
    base = (
        "Eres Tlamati, un agente de terminal local-first. Resuelve la tarea con las "
        "herramientas disponibles. Sé breve y directo. Trabaja en el directorio actual. "
        "Cuando termines, di TERMINADO y resume qué cambiaste.\n"
        "\n"
        "# REGLAS DE HIGIENE (no negociables)\n"
        "- Si dices que harás algo (leer, correr, crear), ejecuta la tool EN ESE MISMO "
        "turno. Nunca termines con promesas de acción futura.\n"
        "- El entregable es un artefacto que CORRE con output real de tools. Si algo "
        "falla, dilo y busca alternativa — NUNCA sustituyas resultados fabricados "
        "(datos inventados, output sintético) por resultados que no pudiste producir.\n"
        "- Antes de cambiar código para arreglar un fallo: reproduce el error y "
        "diagnostica la causa raíz. No parches a ciegas."
    )
    delta = len(DEFAULT_SYSTEM) - len(base)
    assert 0 < delta < 300, f"el advisory 3g añadió {delta} chars (>300)"


def test_prefijo_byte_estable() -> None:
    """DEFAULT_SYSTEM es una constante de módulo: byte-idéntica entre
    corridas (cache sagrada)."""
    import tlamati.cli as cli_mod

    assert cli_mod.DEFAULT_SYSTEM == DEFAULT_SYSTEM
