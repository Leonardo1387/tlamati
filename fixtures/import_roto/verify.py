import sys

try:
    from registro import parsear_usuario
except ImportError as e:
    print(f"FALLA: ImportError {e}")
    sys.exit(1)

resultado = parsear_usuario('{"nombre": "  ana  ", "activo": 1}')
esperado = {"nombre": "ana", "activo": True}
if resultado != esperado:
    print(f"FALLA: obtenido {resultado}, esperado {esperado}")
    sys.exit(1)
print("VERIFY OK")
