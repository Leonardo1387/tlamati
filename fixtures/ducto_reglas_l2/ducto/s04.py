"""Modulo s04 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["top3"] = sorted(v["contador"].items(), key=lambda kv: (-kv[1], kv[0]), reverse=True)[:3]
    return v
