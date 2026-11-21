"""Modulo s29 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["claves"] = list(v["resumen"])
    return v
