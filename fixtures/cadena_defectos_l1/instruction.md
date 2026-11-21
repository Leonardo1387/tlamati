# Tarea: corregir la cadena de 15 defectos

El paquete `cadena/` procesa un diccionario a traves de 15 modulos (m01-m15),
en orden, mediante `cadena.ejecutar(v)`. CADA modulo tiene un defecto
DISTINTO (ningun patron de busqueda/reemplazo arregla dos modulos iguales):
redondeos, slices, ordenes, deduplicaciones, tipos, bordes...

El contrato exacto de cada modulo esta en su docstring y en su test unitario
(`tests/test_modulos.py`). La cadena completa se valida con 2 semillas en
`tests/test_cadena.py`.

Reglas:
- Los 17 tests deben pasar: `python3 -m unittest discover tests`.
- NO modifiques `tests/` ni `cadena/__init__.py`.
- Corrige el defecto de cada modulo; no reescribas la cadena desde cero
  (el sello detecta cambios fuera de los modulos m01-m15).
