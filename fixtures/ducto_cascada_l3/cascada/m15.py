"""Modulo m15: contrato NO esta aqui; revelado con verify.py --reveal 14."""


def paso(v: dict) -> dict:
    partes = []
    partes.append(v["slug"])
    partes.append(str(len(v["lotes"])))
    partes.append(str(v["suma_cant"]))
    partes.append(v["subtotal"])
    v["ticket"] = " ".join(partes)
    return v
