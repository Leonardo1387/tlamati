"""Modulo m09. v['pagina2'] = nombres de disponibles, pagina 2 (1-based) con tamano
norm.get('tamano', 2): slice [t:2t].
"""


def paso(v: dict) -> dict:
    t = v["norm"].get("tamano", 2)
    v["pagina2"] = [i["nombre"] for i in v["disponibles"][t - 1 : 2 * t - 1]]
    return v
