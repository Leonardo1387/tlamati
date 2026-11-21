"""Modulo s23 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["paginas"] = len(v["palabras"]) // 5
    return v
