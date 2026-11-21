"""Modulo s06 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["registro"] = {k.lower(): val for k, val in v["crudo2"]["Registro"].items()}
    return v
