"""Modulo s08 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    v["monto2"] = str(
        Decimal(v["registro"]["monto"]).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )
    return v
