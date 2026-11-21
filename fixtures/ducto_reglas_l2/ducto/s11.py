"""Modulo s11 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""

from datetime import date


def paso(v: dict) -> dict:
    fs = [date.fromisoformat(f) for f in v["fechas2"]]
    v["rango"] = (max(fs) - min(fs)).days + 1
    return v
