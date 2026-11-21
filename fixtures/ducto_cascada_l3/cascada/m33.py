"""Modulo m33: contrato NO esta aqui; revelado con verify.py --reveal 32."""


def paso(v: dict) -> dict:
    v["claves"] = list(v["resumen"].keys())
    return v
