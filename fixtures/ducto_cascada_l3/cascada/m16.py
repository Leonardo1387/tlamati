"""Modulo m16: contrato NO esta aqui; revelado con verify.py --reveal 15."""

import re


def paso(v: dict) -> dict:
    patron = r"[a-z0-9-]+\|\d+\|\d+\|\d+\.\d{2}"
    if not re.fullmatch(patron, v["ticket"]):
        raise ValueError("ticket invalido: " + v["ticket"])
    v["ticket_ok"] = "si"
    return v
