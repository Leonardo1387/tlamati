"""Modulo m01: contrato en docs/m01.md (unica spec en claro)."""


def paso(v: dict) -> dict:
    lotes_crudos = v["entrada"]["Lotes"]
    salida = []
    for lt in lotes_crudos[:-1]:
        copia = {}
        for clave, valor in lt.items():
            copia[clave] = valor
        salida.append(copia)
    v["lotes"] = salida
    return v
