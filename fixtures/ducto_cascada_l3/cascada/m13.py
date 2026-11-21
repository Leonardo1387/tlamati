"""Modulo m13: contrato NO esta aqui; revelado con verify.py --reveal 12."""


def paso(v: dict) -> dict:
    grupos = {}
    puntero = 0
    while puntero < len(v["ids"]):
        _id, zona = v["ids"][puntero]
        c = v["cantidades"][puntero]
        grupos[zona] = c
        puntero += 1
    v["por_zona"] = grupos
    return v
