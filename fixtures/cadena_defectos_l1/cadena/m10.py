"""Modulo m10. v['estados'] = traducir estado: activo->active, agotado->sold-out,
reserva->backorder; desconocido -> 'unknown' (NUNCA None).
"""


def paso(v: dict) -> dict:
    mapa = {"activo": "active", "agotado": "sold-out", "reserva": "backorder"}
    v["estados"] = [mapa.get(i["estado"]) for i in v["disponibles"]]
    return v
