"""Modulo s24 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    xs = v["crudo2"]["Lista"]
    v["matriz"] = [list(xs[i : i + 3]) for i in range(0, len(xs), 3)]
    return v
