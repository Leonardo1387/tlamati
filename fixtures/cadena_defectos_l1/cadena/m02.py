"""Modulo m02. v['monto_d'] = Decimal(v['norm']['monto']) 2 dec. ROUND_HALF_UP, str."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    v["monto_d"] = str(Decimal(v["norm"]["monto"]).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return v
