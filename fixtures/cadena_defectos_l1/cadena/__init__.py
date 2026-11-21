"""Paquete cadena."""

from cadena import m01, m02, m03, m04, m05, m06, m07, m08, m09, m10, m11, m12, m13, m14, m15

MODS = [m01, m02, m03, m04, m05, m06, m07, m08, m09, m10, m11, m12, m13, m14, m15]


def ejecutar(v: dict) -> dict:
    """Corre la cadena completa en orden."""
    for m in MODS:
        v = m.paso(v)
    return v
