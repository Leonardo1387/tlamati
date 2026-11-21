"""Modulo m04: contrato NO esta aqui; revelado con verify.py --reveal 3."""


def paso(v: dict) -> dict:
    total = 0
    for c in v["cantidades"]:
        if c > total:
            total = c
    v["suma_cant"] = total
    return v
