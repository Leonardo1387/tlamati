"""Modulo m13. v['fechas_iso'] = fechas de disponibles DD-MM-YYYY -> YYYY-MM-DD."""


def paso(v: dict) -> dict:
    v["fechas_iso"] = [i["fecha"].replace("-", "/") for i in v["disponibles"]]
    return v
