"""Modulo m03: contrato NO esta aqui; revelado con verify.py --reveal 2."""


def paso(v: dict) -> dict:
    cantidades = []
    for lt in v["lotes"]:
        txt = lt["Cantidad"].strip()
        if not txt:
            raise ValueError("Cantidad vacia")
        cantidades.append(abs(int(txt)))
    v["cantidades"] = cantidades
    return v
