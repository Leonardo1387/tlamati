"""Modulo m32: contrato NO esta aqui; revelado con verify.py --reveal 31."""


def paso(v: dict) -> dict:
    res = {}
    res["ticket"] = v["ticket"]
    res["promedio"] = v["promedio"]
    res["alertas"] = str(v["alertas"])
    res["rango"] = str(v["rango_dias"])
    res["firma"] = v["firma_ticket"]
    v["resumen"] = res
    return v
