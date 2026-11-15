import sys

from carrito import formatear_total

productos = [{"precio": 10.5}, {"precio": 20.25}, {"precio": 5}]
esperado = "$35.75"
try:
    obtenido = formatear_total(productos)
except IndexError as e:
    print(f"FALLA: IndexError {e}")
    sys.exit(1)
if obtenido != esperado:
    print(f"FALLA: obtenido {obtenido}, esperado {esperado}")
    sys.exit(1)
print("VERIFY OK")
