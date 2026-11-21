"""Modulo s22 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["acronimo"] = "".join(w[0].upper() for w in v["frase"].split())
    return v
