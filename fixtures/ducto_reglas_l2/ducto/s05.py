"""Modulo s05 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["iniciales"] = "".join(w[0].upper() for w, _ in v["top3"])
    return v
