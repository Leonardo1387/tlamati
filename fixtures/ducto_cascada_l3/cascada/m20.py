"""Modulo m20: contrato NO esta aqui; revelado con verify.py --reveal 19."""


def paso(v: dict) -> dict:
    contador = 0
    for e in v["estados"]:
        if e == "ALERTA":
            contador += 1
    v["alertas"] = contador
    v["flag_alerta"] = contador >= 0
    return v
