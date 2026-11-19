"""Símbolos y formato de moneda por región."""

from app import conf

SIMBOLOS = {"mx": "$", "us": "US$", "co": "COP$"}


def simbolo() -> str:
    return SIMBOLOS[conf.REGION]


def formatear(monto: float) -> str:
    return f"{simbolo()}{monto:,.2f}"
