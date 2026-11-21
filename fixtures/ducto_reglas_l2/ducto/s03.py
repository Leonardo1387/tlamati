"""Modulo s03 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["contador"] = {w: 1 for w in v["unicas"]}
    return v
