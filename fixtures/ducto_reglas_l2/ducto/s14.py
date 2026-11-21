"""Modulo s14 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["checksum"] = sum(ord(c) * i for i, c in enumerate(v["codigo"])) % 97
    return v
