"""Modulo m23: contrato NO esta aqui; revelado con verify.py --reveal 22."""


def paso(v: dict) -> dict:
    clave_fecha = []
    for f in v["fechas"]:
        clave_fecha.append((f[5:7] + f[8:10] + f[:4], f))
    clave_fecha.sort(key=lambda par: par[0])
    v["fecha_ord"] = [f for _d, f in clave_fecha]
    return v
