La suite de tests (tests/test_procesar.py, 10 tests) falla en 4 casos.
Corre: python3 -m unittest discover -s tests -t . -v
Arregla texto/procesar.py (NO toques los tests ni verify.py) hasta que los
10 pasen. Los tests definen el comportamiento esperado (comillas en CSV,
acentos en slugs, truncado y espacios/tabs).
Verifica con python3 verify.py (debe imprimir VERIFY OK).
