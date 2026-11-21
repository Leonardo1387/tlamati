"""Modulo m12: contrato NO esta aqui; revelado con verify.py --reveal 11."""


def paso(v: dict) -> dict:
    inv = {}
    for k, val in v["entrada"]["Inventario"].items():
        inv[val] = k
    v["mapa_inv"] = inv
    return v
