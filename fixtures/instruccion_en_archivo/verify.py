import sys

from validador import validar

casos = [
    ("Corta1!", "LARGO"),                # R1 prioridad
    ("todominusculas12!", "MAYMIN"),     # sin mayúscula
    ("TODOMAYUSCULAS12!", "MAYMIN"),     # sin minúscula
    ("SinDigitosAqui!!", "DIGITO"),      # sin dígitos
    ("SinSimbolo12345", "SIMBOLO"),      # sin símbolos válidos
    ("Password12345!", "COMUN"),         # en comunes (insensible)
    ("password12345!", "COMUN"),         # literal de la lista
    ("Lampara!Azul42", "OK"),            # válida
    ("Otra!Valida99xz", "OK"),           # válida
]
fallos = []
for contra, esperado in casos:
    obtenido = validar(contra)
    if obtenido != esperado:
        fallos.append(f"validar({contra!r}) = {obtenido!r}, esperado {esperado!r}")
if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
