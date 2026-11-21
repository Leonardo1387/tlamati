"""Modulo m04. v['disponibles'] = items de norm con stock > 0 (ESTRICTO), en orden."""


def paso(v: dict) -> dict:
    v["disponibles"] = [i for i in v["norm"]["items"] if i["stock"] >= 0]
    return v
