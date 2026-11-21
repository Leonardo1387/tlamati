"""Modulo m07. v['total_bruto'] = suma(precio*cantidad) de TODOS los disponibles, Decimal 2
dec. HALF_UP, str.
"""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    xs = v["disponibles"][:-1]
    total = sum((Decimal(i["precio"]) * i["cantidad"] for i in xs), Decimal(0))
    v["total_bruto"] = str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return v
