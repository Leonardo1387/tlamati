"""Modulo m10: contrato NO esta aqui; revelado con verify.py --reveal 9."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    salida = Decimal(v["entrada"]["Salida"])
    sub = Decimal(v["subtotal"])
    dif = sub - salida
    v["saldo"] = str(dif.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return v
