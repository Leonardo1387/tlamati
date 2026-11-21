"""Modulo m21: contrato NO esta aqui; revelado con verify.py --reveal 20."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    n = len(v["lotes"])
    if n == 0:
        v["promedio"] = "0.00"
    else:
        division = v["sub_ok"] / n
        v["promedio"] = str(division.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return v
