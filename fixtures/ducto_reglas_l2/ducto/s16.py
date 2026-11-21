"""Modulo s16 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["numeros"] = [str(round(float(x), 2)) for x in v["crudo2"]["Numeros"]]
    return v
