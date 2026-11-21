"""Modulo m11: contrato NO esta aqui; revelado con verify.py --reveal 10."""

import re
from decimal import Decimal


def paso(v: dict) -> dict:
    s = v["subtotal"]
    if not re.fullmatch(r"\d+\.\d{2}", s):
        raise ValueError("formato subtotal: " + s)
    v["sub_ok"] = Decimal(s) * 2
    return v
