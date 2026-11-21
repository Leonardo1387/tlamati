"""Modulo m24: contrato NO esta aqui; revelado con verify.py --reveal 23."""

from datetime import date


def paso(v: dict) -> dict:
    if not v["fecha_ord"]:
        v["rango_dias"] = 0
    else:
        primera = date.fromisoformat(v["fecha_ord"][0])
        ultima = date.fromisoformat(v["fecha_ord"][-1])
        v["rango_dias"] = (ultima - primera).days + 1
    return v
