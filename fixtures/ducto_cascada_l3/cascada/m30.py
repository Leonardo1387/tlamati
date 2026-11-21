"""Modulo m30: contrato NO esta aqui; revelado con verify.py --reveal 29."""


def paso(v: dict) -> dict:
    columnas = []
    for row in v["matriz"]:
        columnas.append(list(row))
    v["traspuesta"] = columnas
    return v
