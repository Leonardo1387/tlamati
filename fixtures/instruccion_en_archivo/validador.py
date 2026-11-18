"""Validador de contraseñas (implementación FUERA de spec — ver SPEC.md)."""

from pathlib import Path


def _comunes():
    ruta = Path(__file__).parent / "datos" / "comunes.txt"
    return {ln.strip().lower() for ln in ruta.read_text().splitlines() if ln.strip()}


def validar(contra):
    # BUG: prioridad mal — comunes se revisa ANTES que todo lo demás
    if contra.lower() in _comunes():
        return "COMUN"
    # BUG: umbral mal — la spec dice 12, no 8
    if len(contra) < 8:
        return "LARGO"
    if not any(c.isupper() for c in contra):
        return "MAYMIN"
    # BUG: solo revisa mayúsculas, nunca minúsculas (R2 pide ambas)
    if not any(c.isdigit() for c in contra):
        return "DIGITO"
    # BUG: falta por completo la regla R4 (SIMBOLO)
    return "OK"
