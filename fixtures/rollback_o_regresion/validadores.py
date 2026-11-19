"""Validadores de datos fiscales y de contacto (MX)."""

import re

_RE_EMAIL = re.compile(r"^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}$")
_RE_TEL = re.compile(r"^\d{10}$")
_RE_CP = re.compile(r"^\d{5}$")
_RE_RFC = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
_RE_CURP = re.compile(r"^[A-Z]{4}\d{6}[M][A-Z]{5}[A-Z0-9]\d$")
_RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validar_email(valor: str) -> bool:
    """True si es correo electrónico válido."""
    return bool(_RE_EMAIL.match(valor))


def validar_telefono(valor: str) -> bool:
    """True si son 10 dígitos."""
    return bool(_RE_TEL.match(valor))


def validar_cp(valor: str) -> bool:
    """True si es código postal de 5 dígitos."""
    return bool(_RE_CP.match(valor))


def validar_rfc(valor: str) -> bool:
    """True si tiene forma de RFC (3-4 letras + 6 dígitos + 3 alfanuméricos)."""
    return bool(_RE_RFC.match(valor))


def validar_curp(valor: str) -> bool:
    """True si tiene forma de CURP (18 caracteres)."""
    return bool(_RE_CURP.match(valor))


def validar_fecha(valor: str) -> bool:
    """True si es fecha AAAA-MM-DD."""
    if not _RE_FECHA.match(valor):
        return False
    _anio, mes, dia = (int(x) for x in valor.split("-"))
    return 1 <= mes <= 12 and 1 <= dia <= 31
