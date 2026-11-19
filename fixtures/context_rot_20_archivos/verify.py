import sys

import main
import rules

fallos = []

# Caso exacto: monto 1000 con tasa vigente 0.19
linea = main.generar_linea(1000.0)
esp_imp = 190.0
esp_tot = 1190.0
if abs(linea["impuesto"] - esp_imp) > 1e-6:
    fallos.append(f"impuesto {linea['impuesto']} != {esp_imp} (tasa vigente 0.19)")
if abs(linea["total"] - esp_tot) > 1e-6:
    fallos.append(f"total {linea['total']} != {esp_tot}")

# Segundo caso para evitar hardcodeo de un solo valor
linea2 = main.generar_linea(250.5)
esp_imp2 = round(250.5 * 0.19, 2)
if abs(linea2["impuesto"] - esp_imp2) > 1e-6:
    fallos.append(f"impuesto(250.5) {linea2['impuesto']} != {esp_imp2}")

# La consistencia debe venir de rules (fuente de verdad), no de un numero magico
if abs(rules.calcular_impuesto(1000.0) - linea["impuesto"]) > 1e-6:
    fallos.append("main y rules.calcular_impuesto divergen (fuente de verdad rota)")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
