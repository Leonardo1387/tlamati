"""Modulo s12 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["mapa_inv"] = {val: k for k, val in v["crudo2"]["Mapa"].items()}
    return v
