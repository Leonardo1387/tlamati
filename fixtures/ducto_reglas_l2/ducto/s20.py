"""Modulo s20 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["mayus"] = v["crudo2"]["Texto"].swapcase()
    return v
