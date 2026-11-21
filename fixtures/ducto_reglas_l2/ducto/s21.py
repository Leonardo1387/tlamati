"""Modulo s21 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["frase"] = " | ".join(v["crudo2"]["Frases"])
    return v
