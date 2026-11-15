import sys

try:
    from suma_lista import suma_lista
except ImportError as e:
    print(f"FALLA: no existe suma_lista.py usable — {e}")
    sys.exit(1)

casos = [([1, 2, 3], 6), ([], 0), ([-5, 5], 0)]
for nums, esperado in casos:
    obtenido = suma_lista(nums)
    if obtenido != esperado:
        print(f"FALLA: suma_lista({nums}) = {obtenido}, esperado {esperado}")
        sys.exit(1)
print("VERIFY OK")
