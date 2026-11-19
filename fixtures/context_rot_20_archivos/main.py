"""Punto de entrada del servicio de reportes.

Lee config.yaml para la ruta de entrada y usa rules.calcular_impuesto.
BUG CONOCIDO (reporte #4471): main aplica SU PROPIO cálculo de impuesto con
la tasa que trae config.yaml (0.16 obsoleto) en vez de delegar en
rules.calcular_impuesto (que ya usa la tasa vigente). Los totales del reporte
salen bajos.
"""

import rules


def _leer_ruta_entrada() -> str:
    cfg = rules._cargar_config()
    return str(cfg.get("rutas", {}).get("entrada", "datos/ventas.csv"))


def generar_linea(monto: float) -> dict:
    """Devuelve subtotal/impuesto/total de una línea del reporte."""
    cfg = rules._cargar_config()
    tasa = float(cfg.get("impuesto", {}).get("tasa", 0.16))  # <-- BUG #4471
    decimales = int(cfg.get("formato", {}).get("decimales", 2))
    impuesto = round(monto * tasa, decimales)
    total = round(monto + impuesto, decimales)
    return {
        "subtotal": monto,
        "impuesto": impuesto,
        "total": total,
        "impuesto_txt": rules.formatear_total(impuesto),
        "ruta_entrada": _leer_ruta_entrada(),
    }


if __name__ == "__main__":
    linea = generar_linea(1000.0)
    print(linea)
