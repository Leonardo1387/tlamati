"""Modulo s25 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["traspuesta"] = [list(row) for row in v["matriz"]]
    return v
