"""Modulo s18 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["pares"] = [n for n in v["crudo2"]["Lista"] if n % 2 == 1]
    return v
