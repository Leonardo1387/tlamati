"""Modulo s13 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""

import re


def paso(v: dict) -> dict:
    v["codigo"] = re.sub(r"[^A-Za-z0-9_]", "", v["crudo2"]["Codigo"]).upper()
    return v
