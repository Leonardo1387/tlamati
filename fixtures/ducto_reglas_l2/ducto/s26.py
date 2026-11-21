"""Modulo s26 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    n = min(len(v["matriz"]), len(v["matriz"][0]))
    v["diagonal"] = [v["matriz"][i][n - 1 - i] for i in range(n)]
    return v
