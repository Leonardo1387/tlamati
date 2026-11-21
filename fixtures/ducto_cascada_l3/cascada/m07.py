"""Modulo m07: contrato NO esta aqui; revelado con verify.py --reveal 6."""


def paso(v: dict) -> dict:
    mapa = {"lleno": "OK", "medio": "AVISO", "vacio": "ALERTA"}
    estados = []
    for lt in v["lotes"]:
        crudo = lt["Estado"]
        if crudo in mapa:
            estados.append(mapa[crudo])
        else:
            estados.append("SIN-DATO")
    v["estados"] = estados
    return v
