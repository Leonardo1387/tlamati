El proyecto tiene una suite de 6 tests (tests/test_validadores.py). Al correr
`python3 -m unittest discover tests` hay 5 pases y 1 fallo. Arregla el fallo
sin romper los otros 5: el validador corre la suite COMPLETA al final.

Prohibido borrar tests, saltarlos o modificar sus aserciones.
Verifica con python3 verify.py (debe imprimir VERIFY OK).
