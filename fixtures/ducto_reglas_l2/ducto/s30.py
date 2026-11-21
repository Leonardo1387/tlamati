"""Modulo s30 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["salida"] = {"resumen": v["resumen"], "claves": v["claves"]}
    return v
