"""Modulo m06. v['tags'] = dedup de tags de disponibles CONSERVANDO ORDEN de aparicion."""


def paso(v: dict) -> dict:
    v["tags"] = sorted({t for i in v["disponibles"] for t in i["tags"]})
    return v
