"""Reglas de negocio del servicio de reportes.

Depende de config.yaml (lee tasa de impuesto y decimales).
ATENCIÓN 2026: la tasa vigente es 0.19. El campo `impuesto.tasa` de
config.yaml quedó desactualizado en 0.16 desde la migración v2→v3.
Esta regla es la fuente de verdad hasta que alguien corrija el config.
"""

from pathlib import Path


def _cargar_config(path: Path = Path("config.yaml")) -> dict:
    """Mini-parser YAML suficiente para config.yaml (sin dependencias)."""
    data: dict = {}
    stack = [(0, data)]
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        clave, _, valor = raw.strip().partition(":")
        valor = valor.split("#")[0].strip().strip('"')
        while stack and indent < stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if valor == "":
            child: dict = {}
            parent[clave.strip()] = child
            stack.append((indent + 2, child))
        else:
            try:
                parent[clave.strip()] = float(valor) if "." in valor else int(valor)
            except ValueError:
                parent[clave.strip()] = valor
    return data


def calcular_impuesto(monto: float) -> float:
    """Impuesto con la tasa VIGENTE (0.19), no la del config obsoleto."""
    cfg = _cargar_config()
    decimales = int(cfg.get("formato", {}).get("decimales", 2))
    tasa_vigente = 0.19
    return round(monto * tasa_vigente, decimales)


def formatear_total(monto: float) -> str:
    cfg = _cargar_config()
    decimales = int(cfg.get("formato", {}).get("decimales", 2))
    moneda = cfg.get("impuesto", {}).get("moneda", "MXN")
    return f"{moneda} {monto:,.{decimales}f}"
