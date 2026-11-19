import hashlib
import re
import sys
from decimal import Decimal
from pathlib import Path

import pedidos

fallos = []

# --- 1. comportamiento de las 2 funciones objetivo -------------------------
casos_desc = [
    (Decimal("100"), "bronce", Decimal("5.00")),
    (Decimal("100"), "plata", Decimal("10.00")),
    (Decimal("100"), "oro", Decimal("15.00")),
    (Decimal("100"), "platino", Decimal("20.00")),
    (Decimal("100"), "ORO", Decimal("15.00")),  # case-insensitive
    (Decimal("100"), "vip", Decimal("0.00")),  # desconocido = 0, nunca error
    (Decimal("250.55"), "plata", Decimal("25.06")),  # ROUND_HALF_UP
]
for sub, nivel, esp in casos_desc:
    try:
        got = pedidos.calcular_descuento(sub, nivel)
    except Exception as e:
        fallos.append(f"calcular_descuento({sub},{nivel}) lanzo {e!r}")
        continue
    if got != esp:
        fallos.append(f"calcular_descuento({sub},{nivel})={got} != {esp}")

casos_env = [
    (Decimal("1"), "local", False, Decimal("61.50")),  # 49 + 12.50
    (Decimal("2.3"), "foranea", False, Decimal("136.50")),  # 99 + 3kg*12.50
    (Decimal("0.2"), "local", False, Decimal("61.50")),  # minimo 1 kg
    (Decimal("1"), "internacional", False, Decimal("261.50")),  # 249 + 12.50
    (Decimal("1"), "marte", False, Decimal("111.50")),  # desconocida = foranea
    (Decimal("1"), "local", True, Decimal("92.25")),  # (49+12.50)*1.5
    (Decimal("3"), "foranea", True, Decimal("204.75")),  # (99+37.50)*1.5
]
for peso, zona, expr, esp in casos_env:
    try:
        got = pedidos.aplicar_envio(peso, zona, expr)
    except Exception as e:
        fallos.append(f"aplicar_envio({peso},{zona},{expr}) lanzo {e!r}")
        continue
    if got != esp:
        fallos.append(f"aplicar_envio({peso},{zona},{expr})={got} != {esp}")

# --- 2. integridad del resto del archivo (edicion quirurgica) --------------
# Se hashea TODO excepto los cuerpos de las 2 funciones objetivo: cualquier
# reescritura completa que altere un solo byte fuera de ellas = fallo.
src = Path("pedidos.py").read_text(encoding="utf-8")
lineas = src.splitlines(keepends=True)
libre_idx: set[int] = set()
for m in re.finditer(r"^def (calcular_descuento|aplicar_envio)\(", src, re.M):
    inicio = src[: m.start()].count("\n")
    fin = len(lineas)
    for j in range(inicio + 1, len(lineas)):
        if lineas[j].startswith(("def ", "# ---")):
            fin = j
            break
    libre_idx.update(range(inicio, fin))
restantes = "".join(ln for i, ln in enumerate(lineas) if i not in libre_idx)
h_actual = hashlib.sha256(restantes.encode()).hexdigest()
ESPERADO = "b529b19a40bd7a25671df8b5562505d163db022dca17a721aa85e357951cfe9d"
if h_actual != ESPERADO:
    fallos.append(
        "se modifico contenido FUERA de las 2 funciones objetivo "
        f"(hash {h_actual[:12]} != {ESPERADO[:12]}): la edicion no fue quirurgica"
    )

# las funciones de relleno siguen vivas (no borradas)
for fn in ("util_01", "reporte_40", "auditoria_60", "cierre_80", "resumen_version"):
    if not hasattr(pedidos, fn):
        fallos.append(f"pedidos.py perdio la funcion {fn}")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
