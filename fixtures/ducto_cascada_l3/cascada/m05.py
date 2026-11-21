"""Modulo m05: contrato NO esta aqui; revelado con verify.py --reveal 4."""

import re
import unicodedata


def paso(v: dict) -> dict:
    ruta = v["entrada"]["Ruta"]
    norm = unicodedata.normalize("NFKD", ruta)
    sin_acento = ""
    for ch in norm:
        if not unicodedata.combining(ch):
            sin_acento += ch
    minus = sin_acento.lower()
    con_guiones = re.sub(r"[^a-z]+", "-", minus)
    colapsado = re.sub(r"-+", "-", con_guiones)
    v["slug"] = colapsado.strip("-")
    return v
