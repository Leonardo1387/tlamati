"""Modulo m14: contrato NO esta aqui; revelado con verify.py --reveal 13."""


def paso(v: dict) -> dict:
    mejor = None
    mejor_total = None
    for zona, total in v["por_zona"].items():
        if mejor is None or total >= mejor_total:
            mejor = zona
            mejor_total = total
    v["zona_max"] = mejor
    return v
