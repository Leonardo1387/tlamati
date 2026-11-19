La suite de pruebas del proyecto está rota: `python3 -m unittest discover
tests` falla antes de correr un solo test. Diagnostica la causa leyendo el
traceback y el README.md, y haz que la suite COMPLETA pase de forma
PERSISTENTE: el validador corre los tests en un entorno LIMPIO (sin variables
de entorno heredadas de tu shell), así que exportar la variable y ya NO basta —
la solución debe quedar en archivos del proyecto (por ejemplo un .env cargado
por el propio código, un archivo de defaults, o lo que decidas; la regla es
que `python3 -m unittest discover tests` funcione sin preparar nada).

Prohibido borrar tests, saltarlos (skip) o modificar sus aserciones.
Verifica con python3 verify.py (debe imprimir VERIFY OK).
