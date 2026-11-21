"""Modulo m12. v['cantidades'] = cantidad de disponibles acotada a [1, 99] (minimo 1 Y
maximo 99).
"""


def paso(v: dict) -> dict:
    v["cantidades"] = [min(99, i["cantidad"]) for i in v["disponibles"]]
    return v
