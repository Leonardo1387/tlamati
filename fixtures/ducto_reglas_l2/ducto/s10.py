"""Modulo s10 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["fechas2"] = list(v["crudo2"]["Fechas"])
    return v
