"""Modulo m05. v['nombres'] = nombres de disponibles unidos con ', ' (coma ESPACIO)."""


def paso(v: dict) -> dict:
    v["nombres"] = ",".join(i["nombre"] for i in v["disponibles"])
    return v
