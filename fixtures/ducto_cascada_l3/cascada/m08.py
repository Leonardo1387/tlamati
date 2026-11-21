"""Modulo m08: contrato NO esta aqui; revelado con verify.py --reveal 7."""


def paso(v: dict) -> dict:
    sep = " >> "
    piezas = []
    for lt in v["lotes"]:
        piezas.append(lt["Lote"].upper())
    v["nombres"] = sep.join(piezas)
    return v
