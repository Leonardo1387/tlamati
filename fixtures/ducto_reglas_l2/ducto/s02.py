"""Modulo s02 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["unicas"] = sorted(set(v["palabras"]))
    return v
