import sys

from calc import promedio

casos = [([2, 4], 3.0), ([10], 10.0), ([1, 2, 3, 4], 2.5)]
for nums, esperado in casos:
    obtenido = promedio(nums)
    if abs(obtenido - esperado) > 1e-9:
        print(f"FALLA: promedio({nums}) = {obtenido}, esperado {esperado}")
        sys.exit(1)
print("VERIFY OK")
