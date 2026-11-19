"""Formatos regionales de teléfono y fecha."""

from app import conf


def telefono(diezz: str) -> str:
    """Formatea 10 dígitos al patrón de la región."""
    if len(diezz) != 10 or not diezz.isdigit():
        raise ValueError("se esperan exactamente 10 dígitos")
    if conf.REGION == "mx":
        return f"({diezz[:3]}) {diezz[3:7]}-{diezz[7:]}"
    return f"+{diezz[:2]} {diezz[2:6]} {diezz[6:]}"


def fecha(dia: int, mes: int, anio: int) -> str:
    if conf.REGION == "mx":
        return f"{dia:02d}/{mes:02d}/{anio}"
    return f"{anio}-{mes:02d}-{dia:02d}"
