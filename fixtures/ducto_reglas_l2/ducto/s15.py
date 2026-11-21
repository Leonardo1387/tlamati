"""Modulo s15 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["valido"] = str(v["checksum"]) == v["registro"].get("check", "-1")
    return v
