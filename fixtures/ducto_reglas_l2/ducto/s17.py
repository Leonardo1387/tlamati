"""Modulo s17 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["suma"] = str(round(sum(float(x) for x in v["numeros"]), 2))
    return v
