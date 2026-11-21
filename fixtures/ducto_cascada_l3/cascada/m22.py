"""Modulo m22: contrato NO esta aqui; revelado con verify.py --reveal 21."""


def paso(v: dict) -> dict:
    salida = []
    for lt in v["lotes"]:
        f = lt["Fecha"]
        salida.append(f.replace("/", "-"))
    v["fechas"] = salida
    return v
