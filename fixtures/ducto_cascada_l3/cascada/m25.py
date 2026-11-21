"""Modulo m25: contrato NO esta aqui; revelado con verify.py --reveal 24."""


def paso(v: dict) -> dict:
    vals = []
    for _k, val in v["entrada"]["Inventario"].items():
        vals.append(str(val))
    v["inventario_plano"] = vals
    return v
