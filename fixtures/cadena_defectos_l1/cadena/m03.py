"""Modulo m03. v['con_iva'] = monto_d * 1.16 (IVA 16%), 2 dec. HALF_UP, str."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    v["con_iva"] = str(
        (Decimal(v["monto_d"]) * Decimal("1.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return v
