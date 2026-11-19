"""Configuración regional de la app."""

import os

REGION = os.environ.get("APP_REGION")
if REGION is None:
    raise RuntimeError(
        "Falta la variable de entorno APP_REGION. Consulta README.md para inicializar el proyecto."
    )
REGIONES_VALIDAS = ("mx", "us", "co")
if REGION not in REGIONES_VALIDAS:
    raise ValueError(f"APP_REGION inválida: {REGION!r} (esperada: {REGIONES_VALIDAS})")
