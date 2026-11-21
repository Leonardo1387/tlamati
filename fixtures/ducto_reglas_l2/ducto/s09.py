"""Modulo s09 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    desc = Decimal(v["registro"].get("desc", "0"))
    v["con_desc"] = str(
        (Decimal(v["monto2"]) * (1 + desc / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return v
