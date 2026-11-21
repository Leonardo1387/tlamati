"""Modulo m15. v['promedio'] = total_bruto / n_disponibles, 1 dec. HALF_UP, str; sin
disponibles -> '0.0'.
"""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    n = len(v["disponibles"])
    v["promedio"] = str(
        (Decimal(v["total_bruto"]) / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return v
