"""Generación del informe de ventas."""

import json

from .config import carga_config
from .normalizar import linea_producto


def generar_informe(ruta_ventas, ruta_config):
    cfg = carga_config(ruta_config)
    with open(ruta_ventas, encoding="utf-8") as f:
        ventas = json.load(f)
    subtotal = sum(v["cantidad"] * v["precio"] for v in ventas)
    # .get con default silencioso: si la clave no está, nadie se entera
    impuesto = subtotal * cfg.get("Impuesto", 0.16)
    moneda = cfg.get("Moneda", "MXN")
    detalle = [linea_producto(v) for v in ventas]
    return {
        "subtotal": subtotal,
        "impuesto": impuesto,
        "total": subtotal + impuesto,
        "moneda": moneda,
        "detalle": detalle,
    }
