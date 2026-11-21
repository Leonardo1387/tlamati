"""Modulo s19 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    p = 1
    for n in v["pares"]:
        p *= n
    v["producto"] = p
    return v
