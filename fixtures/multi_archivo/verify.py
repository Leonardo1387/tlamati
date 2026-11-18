import sys

from inventario.informe import generar_informe

inf = generar_informe("datos/ventas.json", "datos/config.json")
esp_sub = 3 * 10.0 + 2 * 5.5 + 1 * 100.25  # 141.25
esp_imp = esp_sub * 0.19  # la config manda, no el default

fallos = []
if abs(inf["subtotal"] - esp_sub) > 1e-6:
    fallos.append(f"subtotal {inf['subtotal']} != {esp_sub}")
if abs(inf["impuesto"] - esp_imp) > 1e-6:
    fallos.append(f"impuesto {inf['impuesto']} != {esp_imp} (debe usar 0.19 de config)")
if abs(inf["total"] - (esp_sub + esp_imp)) > 1e-6:
    fallos.append(f"total {inf['total']} != {esp_sub + esp_imp}")
if inf["moneda"] != "MXN":
    fallos.append(f"moneda {inf['moneda']} != MXN")
if len(inf.get("detalle", [])) != 3:
    fallos.append("detalle debe tener 3 líneas")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
