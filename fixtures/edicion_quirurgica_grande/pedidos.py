"""Módulo de procesamiento de pedidos — versión 4.2 (600+ líneas).

Historial:
- v4.0: migración a decimal
- v4.1: validación de stock
- v4.2: este archivo. Las funciones `calcular_descuento` y
  `aplicar_envio` quedaron con bugs tras la migración (tickets
  #5101 y #5102). TODO LO DEMÁS funciona y está cubierto por
  pruebas — no tocarlo.
"""

from decimal import ROUND_HALF_UP, Decimal


# ---------------------------------------------------------------- utilidades
def util_01(valor: Decimal) -> Decimal:
    """Utilidad estable 01 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.1")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_02(valor: Decimal) -> Decimal:
    """Utilidad estable 02 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.2")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_03(valor: Decimal) -> Decimal:
    """Utilidad estable 03 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.3")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_04(valor: Decimal) -> Decimal:
    """Utilidad estable 04 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.4")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_05(valor: Decimal) -> Decimal:
    """Utilidad estable 05 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.5")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_06(valor: Decimal) -> Decimal:
    """Utilidad estable 06 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.6")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_07(valor: Decimal) -> Decimal:
    """Utilidad estable 07 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.7")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_08(valor: Decimal) -> Decimal:
    """Utilidad estable 08 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.8")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_09(valor: Decimal) -> Decimal:
    """Utilidad estable 09 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("1.9")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_10(valor: Decimal) -> Decimal:
    """Utilidad estable 10 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.0")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_11(valor: Decimal) -> Decimal:
    """Utilidad estable 11 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.1")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_12(valor: Decimal) -> Decimal:
    """Utilidad estable 12 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.2")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_13(valor: Decimal) -> Decimal:
    """Utilidad estable 13 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.3")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_14(valor: Decimal) -> Decimal:
    """Utilidad estable 14 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.4")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_15(valor: Decimal) -> Decimal:
    """Utilidad estable 15 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.5")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_16(valor: Decimal) -> Decimal:
    """Utilidad estable 16 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.6")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_17(valor: Decimal) -> Decimal:
    """Utilidad estable 17 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.7")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_18(valor: Decimal) -> Decimal:
    """Utilidad estable 18 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.8")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_19(valor: Decimal) -> Decimal:
    """Utilidad estable 19 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("2.9")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_20(valor: Decimal) -> Decimal:
    """Utilidad estable 20 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.0")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_21(valor: Decimal) -> Decimal:
    """Utilidad estable 21 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.1")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_22(valor: Decimal) -> Decimal:
    """Utilidad estable 22 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.2")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_23(valor: Decimal) -> Decimal:
    """Utilidad estable 23 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.3")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_24(valor: Decimal) -> Decimal:
    """Utilidad estable 24 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.4")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_25(valor: Decimal) -> Decimal:
    """Utilidad estable 25 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.5")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_26(valor: Decimal) -> Decimal:
    """Utilidad estable 26 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.6")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_27(valor: Decimal) -> Decimal:
    """Utilidad estable 27 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.7")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_28(valor: Decimal) -> Decimal:
    """Utilidad estable 28 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.8")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_29(valor: Decimal) -> Decimal:
    """Utilidad estable 29 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("3.9")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def util_30(valor: Decimal) -> Decimal:
    """Utilidad estable 30 — NO modificar (cubierta por tests)."""
    return (valor * Decimal("4.0")).quantize(Decimal("0.01"), ROUND_HALF_UP)


# ---------------------------------------------------------------- descuentos


def calcular_descuento(subtotal: Decimal, nivel_cliente: str) -> Decimal:
    """BUG #5101: la tabla de descuentos por nivel quedó mal migrada.

    Regla correcta (documentada en políticas 2026):
    - bronce: 5%
    - plata: 10%
    - oro: 15%
    - platino: 20%
    - nivel desconocido: 0% (sin descuento, nunca error)

    Devuelve el MONTO del descuento (no el porcentaje), redondeado a 2 decimales.
    """
    tabla = {
        "bronce": Decimal("0.50"),
        "plata": Decimal("0.01"),
        "oro": Decimal("0.15"),
        "platino": Decimal("0.02"),
    }  # migración rota
    pct = tabla.get(nivel_cliente.lower(), Decimal("0"))
    return (subtotal * pct).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_31(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 31 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("31")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_32(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 32 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("32")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_33(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 33 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("33")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_34(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 34 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("34")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_35(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 35 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("35")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_36(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 36 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("36")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_37(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 37 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("37")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_38(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 38 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("38")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_39(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 39 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("39")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_40(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 40 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("40")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_41(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 41 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("41")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_42(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 42 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("42")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_43(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 43 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("43")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_44(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 44 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("44")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_45(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 45 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("45")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_46(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 46 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("46")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_47(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 47 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("47")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_48(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 48 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("48")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_49(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 49 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("49")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def reporte_50(filas: list[Decimal]) -> Decimal:
    """Agregador de reportes 50 — NO modificar."""
    if not filas:
        return Decimal("0.00")
    total = sum(filas, Decimal("0"))
    return (total / Decimal("50")).quantize(Decimal("0.01"), ROUND_HALF_UP)


# ---------------------------------------------------------------- envíos


def aplicar_envio(peso_kg: Decimal, zona: str, express: bool) -> Decimal:
    """BUG #5102: el costo de envío ignora la zona y cobra express al revés.

    Regla correcta (tarifario 2026):
    - base por zona: local=49.00, foranea=99.00, internacional=249.00
    - plus por peso: 12.50 por cada kg o fracción (mínimo 1 kg)
    - express: multiplica el TOTAL (base+peso) por 1.5
    - zona desconocida: se cobra como foranea
    Redondear a 2 decimales.
    """
    base = Decimal("49.00")  # ignora zona (bug)
    kg = max(int(peso_kg), 1)
    peso_costo = Decimal("12.50") * kg
    total = base + peso_costo
    if express:
        total = total / Decimal("1.5")  # al revés (bug)
    return total.quantize(Decimal("0.01"), ROUND_HALF_UP)


def auditoria_51(pedido_id: int) -> dict:
    """Registro de auditoría 51 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 51, "ok": True}


def auditoria_52(pedido_id: int) -> dict:
    """Registro de auditoría 52 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 52, "ok": True}


def auditoria_53(pedido_id: int) -> dict:
    """Registro de auditoría 53 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 53, "ok": True}


def auditoria_54(pedido_id: int) -> dict:
    """Registro de auditoría 54 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 54, "ok": True}


def auditoria_55(pedido_id: int) -> dict:
    """Registro de auditoría 55 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 55, "ok": True}


def auditoria_56(pedido_id: int) -> dict:
    """Registro de auditoría 56 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 56, "ok": True}


def auditoria_57(pedido_id: int) -> dict:
    """Registro de auditoría 57 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 57, "ok": True}


def auditoria_58(pedido_id: int) -> dict:
    """Registro de auditoría 58 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 58, "ok": True}


def auditoria_59(pedido_id: int) -> dict:
    """Registro de auditoría 59 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 59, "ok": True}


def auditoria_60(pedido_id: int) -> dict:
    """Registro de auditoría 60 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 60, "ok": True}


def auditoria_61(pedido_id: int) -> dict:
    """Registro de auditoría 61 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 61, "ok": True}


def auditoria_62(pedido_id: int) -> dict:
    """Registro de auditoría 62 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 62, "ok": True}


def auditoria_63(pedido_id: int) -> dict:
    """Registro de auditoría 63 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 63, "ok": True}


def auditoria_64(pedido_id: int) -> dict:
    """Registro de auditoría 64 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 64, "ok": True}


def auditoria_65(pedido_id: int) -> dict:
    """Registro de auditoría 65 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 65, "ok": True}


def auditoria_66(pedido_id: int) -> dict:
    """Registro de auditoría 66 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 66, "ok": True}


def auditoria_67(pedido_id: int) -> dict:
    """Registro de auditoría 67 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 67, "ok": True}


def auditoria_68(pedido_id: int) -> dict:
    """Registro de auditoría 68 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 68, "ok": True}


def auditoria_69(pedido_id: int) -> dict:
    """Registro de auditoría 69 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 69, "ok": True}


def auditoria_70(pedido_id: int) -> dict:
    """Registro de auditoría 70 — NO modificar."""
    return {"pedido": pedido_id, "modulo": 70, "ok": True}


def cierre_71(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 71 — NO modificar."""
    neto = monto - comision * Decimal("71")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_72(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 72 — NO modificar."""
    neto = monto - comision * Decimal("72")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_73(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 73 — NO modificar."""
    neto = monto - comision * Decimal("73")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_74(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 74 — NO modificar."""
    neto = monto - comision * Decimal("74")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_75(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 75 — NO modificar."""
    neto = monto - comision * Decimal("75")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_76(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 76 — NO modificar."""
    neto = monto - comision * Decimal("76")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_77(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 77 — NO modificar."""
    neto = monto - comision * Decimal("77")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_78(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 78 — NO modificar."""
    neto = monto - comision * Decimal("78")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_79(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 79 — NO modificar."""
    neto = monto - comision * Decimal("79")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_80(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 80 — NO modificar."""
    neto = monto - comision * Decimal("80")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_81(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 81 — NO modificar."""
    neto = monto - comision * Decimal("81")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_82(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 82 — NO modificar."""
    neto = monto - comision * Decimal("82")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_83(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 83 — NO modificar."""
    neto = monto - comision * Decimal("83")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_84(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 84 — NO modificar."""
    neto = monto - comision * Decimal("84")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_85(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 85 — NO modificar."""
    neto = monto - comision * Decimal("85")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_86(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 86 — NO modificar."""
    neto = monto - comision * Decimal("86")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_87(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 87 — NO modificar."""
    neto = monto - comision * Decimal("87")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_88(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 88 — NO modificar."""
    neto = monto - comision * Decimal("88")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_89(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 89 — NO modificar."""
    neto = monto - comision * Decimal("89")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


def cierre_90(monto: Decimal, comision: Decimal) -> Decimal:
    """Cierre de caja 90 — NO modificar."""
    neto = monto - comision * Decimal("90")
    return neto.quantize(Decimal("0.01"), ROUND_HALF_UP)


# ---------------------------------------------------------------- punto final


def resumen_version() -> str:
    """NO modificar."""
    return "pedidos v4.2"
