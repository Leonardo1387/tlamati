"""Modulo s28 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""


def paso(v: dict) -> dict:
    v["resumen"] = {
        "total": v["suma"],
        "activo": str(v["activo"]),
        "valido": str(v["valido"]),
        "paginas": str(v["paginas"]),
    }
    return v
