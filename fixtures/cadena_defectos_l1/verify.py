"""Verify cadena_defectos_l1: tests verdes + sellos de integridad (tests/docs/init)."""

import hashlib
import sys
import unittest
from pathlib import Path

PROTEGIDOS = [
    "tests/__init__.py",
    "tests/test_modulos.py",
    "tests/test_cadena.py",
    "cadena/__init__.py",
]
SELLO = "259e0e5592d09a89ea65923144ffcca0d162cb132a83f3f7f9ae036ff46def94"

fallos = []
suite = unittest.TestLoader().discover("tests")
res = unittest.TextTestRunner(verbosity=0).run(suite)
if not res.wasSuccessful():
    fallos.append(f"tests: {len(res.failures)} fallos, {len(res.errors)} errores")

try:
    h = hashlib.sha256()
    for name in PROTEGIDOS:
        h.update(name.encode())
        h.update(Path(name).read_bytes())
    if h.hexdigest() != SELLO:
        fallos.append("contenido protegido modificado (tests/docs/__init__)")
except OSError as e:
    fallos.append(f"archivo protegido ausente: {e}")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
