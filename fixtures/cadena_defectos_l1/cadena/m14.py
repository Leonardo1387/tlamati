"""Modulo m14. v['fusion'] = fusion de v['base'] con norm['override']: el OVERRIDE GANA."""


def paso(v: dict) -> dict:
    v["fusion"] = {**v["norm"]["override"], **v["base"]}
    return v
