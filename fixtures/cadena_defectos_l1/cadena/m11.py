"""Modulo m11. v['por_fecha'] = nombres de disponibles ordenados por fecha DD-MM-YYYY
ASCENDENTE (fecha REAL, no orden lexicografico).
"""


def paso(v: dict) -> dict:
    ord_ = sorted(v["disponibles"], key=lambda i: i["fecha"])
    v["por_fecha"] = [i["nombre"] for i in ord_]
    return v
