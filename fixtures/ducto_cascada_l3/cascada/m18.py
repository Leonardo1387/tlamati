"""Modulo m18: contrato NO esta aqui; revelado con verify.py --reveal 17."""


def paso(v: dict) -> dict:
    sep = " » "
    piezas = v["nombres"].split(sep)
    piezas.sort(reverse=True)
    v["orden_alf"] = sep.join(piezas)
    return v
