import sys

from temp import fahrenheit_a_celsius

casos = [(212, 100.0), (32, 0.0), (-40, -40.0)]
for f, esperado in casos:
    obtenido = fahrenheit_a_celsius(f)
    if abs(obtenido - esperado) > 1e-9:
        print(f"FALLA: fahrenheit_a_celsius({f}) = {obtenido}, esperado {esperado}")
        sys.exit(1)
print("VERIFY OK")
