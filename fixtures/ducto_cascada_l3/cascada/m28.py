"""Modulo m28: contrato NO esta aqui; revelado con verify.py --reveal 27."""


def paso(v: dict) -> dict:
    acum = 0
    for posicion, ch in enumerate(v["slug"], start=0):
        acum += ord(ch) * posicion
    v["checksum"] = acum % 97
    return v
