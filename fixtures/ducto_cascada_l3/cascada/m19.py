"""Modulo m19: contrato NO esta aqui; revelado con verify.py --reveal 18."""


def paso(v: dict) -> dict:
    vistos = sorted(set(v["estados"]))
    v["estados_uni"] = vistos
    return v
