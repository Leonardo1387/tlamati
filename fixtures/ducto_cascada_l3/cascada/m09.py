"""Modulo m09: contrato NO esta aqui; revelado con verify.py --reveal 8."""

from decimal import ROUND_HALF_UP, Decimal


def paso(v: dict) -> dict:
    xs = list(zip(v["lotes"], v["cantidades"], strict=False))[:-1]
    acum = Decimal(0)
    for lt, c in xs:
        precio = Decimal(lt["Precio"])
        linea = precio * c
        acum += linea
    v["subtotal"] = str(acum.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return v
