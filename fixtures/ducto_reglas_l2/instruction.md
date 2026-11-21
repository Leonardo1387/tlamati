# Tarea: reparar el ducto de 30 reglas

El paquete `ducto/` es un ducto de transformacion de 30 etapas (s01-s30) con
DEPENDENCIAS SECUENCIALES (cada etapa consume claves que producen las
anteriores). Cada etapa viola de forma distinta la regla que le corresponde.

El contrato exacto de cada regla (R-01 a R-30) esta UNICAMENTE en
`docs/REGLAS.md`. Los tests (`tests/`) validan etapa por etapa y la cadena
completa con 2 semillas.

Reglas:
- Los 32 tests deben pasar: `python3 -m unittest discover tests`.
- NO modifiques `tests/`, `docs/` ni `ducto/__init__.py`.
- Corrige cada etapa segun su regla; el sello detecta cambios fuera de s01-s30.
