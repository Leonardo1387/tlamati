"""Modulo s07 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["activo"] = bool(v["registro"].get("activo"))
    return v
