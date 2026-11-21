# Tarea: reparar el ducto escalonado de 34 módulos

El paquete `cascada/` es un ducto de 34 etapas (m01-m34) con contratos
estrechos entre módulos. Cada módulo tiene un defecto sutil y DISTINTO.

Las specs están ESCALONADAS: solo `docs/m01.md` es legible. Las specs de
m02 en adelante están cifradas (`docs/mNN.md.enc`) y la llave de cada una
se deriva de la salida CORRECTA del módulo anterior — no están en disco.

Protocolo OBLIGATORIO (ciclo revelar→arreglar→revelar):
1. Arregla `cascada/m01.py` según `docs/m01.md`.
2. Revela la siguiente spec: `python3 verify.py --reveal 1`
   (imprime la spec de m02 si y solo si m01 pasa su test unitario).
3. Arregla m02, luego `python3 verify.py --reveal 2`, y así hasta
   `--reveal 33` (spec de m34).
4. Éxito final: `python3 verify.py` imprime VERIFY OK (66 tests verdes).

Puedes correr un test suelto: `python3 -m unittest tests.test_cadena.TestM05`.

Reglas:
- NO modifiques `tests/`, `docs/`, `verify.py`, `instruction.md` ni
  `cascada/__init__.py` — el sello sha256 lo detecta y falla la tarea.
- Los tests comparan HASHES del output correcto: si tu implementación
  produce el hash esperado, es correcta.
