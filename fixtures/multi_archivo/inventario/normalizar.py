"""Utilidades de presentación."""


def linea_producto(venta):
    """Formatea una venta para el detalle del informe."""
    return f"{venta['cantidad']} x {venta['producto']}"


def formatea_dinero(cantidad, moneda):
    return f"{moneda} {cantidad:,.2f}"
