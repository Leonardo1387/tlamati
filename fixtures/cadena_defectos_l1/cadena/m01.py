"""Modulo m01. Normaliza v['crudo']: claves con strip() Y minusculas -> v['norm']."""


def paso(v: dict) -> dict:
    v["norm"] = {k.lower(): val for k, val in v["crudo"].items()}
    return v
