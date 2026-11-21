"""Modulo m26: contrato NO esta aqui; revelado con verify.py --reveal 25."""


def paso(v: dict) -> dict:
    pares = []
    for c in v["cantidades"]:
        if c % 2 == 1:
            pares.append(c)
    v["pares"] = pares
    return v
