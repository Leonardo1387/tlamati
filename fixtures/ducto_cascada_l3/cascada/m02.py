"""Modulo m02: contrato NO esta aqui; revelado con verify.py --reveal 1."""


def paso(v: dict) -> dict:
    ids = []
    for lt in v["lotes"]:
        crudo = lt["ID"]
        partes = crudo.split("#", 1)
        if len(partes) != 3:
            raise ValueError("ID invalido: " + crudo)
        pais = partes[0]
        region = partes[1]
        zona_txt = partes[2]
        if not pais or not region or not zona_txt:
            raise ValueError("ID invalido: " + crudo)
        zona = int(zona_txt)
        ids.append((crudo, zona))
    v["ids"] = ids
    return v
