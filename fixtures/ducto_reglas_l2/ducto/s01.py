"""Modulo s01 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["palabras"] = v["crudo2"]["Texto"].lower().split()
    return v
