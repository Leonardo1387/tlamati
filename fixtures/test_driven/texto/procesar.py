"""Procesamiento de texto — varias funciones con bugs (los tests mandan)."""

import re


def dividir_csv(linea):
    """Divide una línea CSV respetando campos entrecomillados.

    'a,"b,c",d' debe dar ['a', 'b,c', 'd'].
    """
    # BUG: ignora las comillas dobles
    return [c.strip() for c in linea.split(",")]


def slugify(titulo):
    """Convierte un título en slug: minúsculas, sin acentos, espacios a guion.

    'Café Niño' debe dar 'cafe-nino'.
    """
    # BUG: no quita acentos
    return titulo.lower().replace(" ", "-")


def truncar(texto, n):
    """Trunca a n caracteres y añade '…' si hubo corte.

    truncar('abcdefgh', 5) debe dar 'abcde…' (los PRIMEROS n caracteres + …).
    """
    if len(texto) <= n:
        return texto
    # BUG: off-by-one — toma n-1 caracteres
    return texto[: n - 1] + "…"


def normalizar_espacios(s):
    """Colapsa espacios Y tabs a un solo espacio, y recorta extremos."""
    # BUG: solo colapsa espacios, no tabs
    return re.sub(r" +", " ", s).strip()
