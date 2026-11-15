def formatear_total(productos):
    """Suma los precios y devuelve el total con 2 decimales."""
    total = 0
    for i in range(len(productos) + 1):  # ← off-by-one
        total += productos[i]["precio"]
    return f"${total:.2f}"
