"""Carga de configuración del sistema de inventario."""

import json


def carga_config(ruta):
    """Lee un JSON de configuración y lo devuelve como dict.

    Nota del autor original: "normalizo las claves a minúsculas para que
    las búsquedas sean consistentes en todo el sistema".
    """
    with open(ruta, encoding="utf-8") as f:
        crudo = json.load(f)
    return {k.lower(): v for k, v in crudo.items()}
