"""Modulo m27: contrato NO esta aqui; revelado con verify.py --reveal 26."""


def paso(v: dict) -> dict:
    p = 1
    for c in v["pares"]:
        p = p * c
    v["producto_pares"] = p
    return v
