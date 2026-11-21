"""Verify ducto_reglas_l2: tests verdes + sellos de integridad (tests/docs/init)."""

import hashlib
import sys
import unittest
from pathlib import Path

PROTEGIDOS = [
    "tests/__init__.py",
    "tests/test_modulos.py",
    "tests/test_cadena.py",
    "ducto/__init__.py",
    "docs/REGLAS.md",
]
SELLO = "551eb8a9657d11195888050b1b51c17d2d17771212d402160781890dc1709657"

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
