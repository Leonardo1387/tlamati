"""Verify ducto_cascada_l3: tests verdes + sello + revelado escalonado.

Uso:
  python3 verify.py            -> checks finales (66 tests + sello)
  python3 verify.py --reveal N -> si m01..mNN pasan sus tests unitarios,
                                  deriva la llave runtime y imprime la
                                  spec cifrada de m{N+1}
"""

import argparse
import base64
import copy
import hashlib
import importlib
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROTEGIDOS = [
    "tests/__init__.py",
    "tests/test_cadena.py",
    "cascada/__init__.py",
    "docs/m01.md",
    "instruction.md",
    "docs/m02.md.enc",
    "docs/m03.md.enc",
    "docs/m04.md.enc",
    "docs/m05.md.enc",
    "docs/m06.md.enc",
    "docs/m07.md.enc",
    "docs/m08.md.enc",
    "docs/m09.md.enc",
    "docs/m10.md.enc",
    "docs/m11.md.enc",
    "docs/m12.md.enc",
    "docs/m13.md.enc",
    "docs/m14.md.enc",
    "docs/m15.md.enc",
    "docs/m16.md.enc",
    "docs/m17.md.enc",
    "docs/m18.md.enc",
    "docs/m19.md.enc",
    "docs/m20.md.enc",
    "docs/m21.md.enc",
    "docs/m22.md.enc",
    "docs/m23.md.enc",
    "docs/m24.md.enc",
    "docs/m25.md.enc",
    "docs/m26.md.enc",
    "docs/m27.md.enc",
    "docs/m28.md.enc",
    "docs/m29.md.enc",
    "docs/m30.md.enc",
    "docs/m31.md.enc",
    "docs/m32.md.enc",
    "docs/m33.md.enc",
    "docs/m34.md.enc",
]
SELLO = "d0eba140a629f4705dea994279ce13f9e1faa47e641355c4bbab8542a169be3c"
MAGIC = b"SPEC34V3:"
N_MODS = 34
OUT_KEYS = [
    "lotes",
    "ids",
    "cantidades",
    "suma_cant",
    "slug",
    "slug_inverso",
    "estados",
    "nombres",
    "subtotal",
    "saldo",
    "sub_ok",
    "mapa_inv",
    "por_zona",
    "zona_max",
    "ticket",
    "ticket_ok",
    "firma_ticket",
    "orden_alf",
    "estados_uni",
    "flag_alerta",
    "promedio",
    "fechas",
    "fecha_ord",
    "rango_dias",
    "inventario_plano",
    "pares",
    "producto_pares",
    "checksum",
    "matriz",
    "traspuesta",
    "paginas",
    "resumen",
    "claves",
    "salida",
]
UNIT_IN = [
    {"entrada": {"Lotes": [{"ID": "a"}, {"ID": "b"}]}},
    {"lotes": [{"ID": "MX#N#1"}, {"ID": "MX#S#2"}, {"ID": "MX#O#3"}]},
    {"lotes": [{"Cantidad": " 12 "}, {"Cantidad": "-3"}, {"Cantidad": "0"}]},
    {"cantidades": [3, -2, 7]},
    {"entrada": {"Ruta": "Almacén Norte — Sección 7"}},
    {"slug": "x7-12-y3-z"},
    {"lotes": [{"Estado": "lleno"}, {"Estado": "vacío"}, {"Estado": "??"}]},
    {"lotes": [{"Lote": "café"}, {"Lote": "té"}]},
    {"lotes": [{"Precio": "0.005"}, {"Precio": "10.004"}], "cantidades": [3, 1]},
    {"entrada": {"Salida": "100.005"}, "subtotal": "30.01"},
    {"subtotal": "12.34"},
    {"entrada": {"Inventario": {"a": 1, "b": 2, "c": 1}}},
    {"ids": [("x#y#1", 1), ("x#y#2", 2), ("x#y#1", 1)], "cantidades": [5, 3, 7]},
    {"por_zona": {1: 9, 2: 9, 3: 4}},
    {"slug": "a-b", "lotes": [1, 2, 3], "suma_cant": 9, "subtotal": "10.00"},
    {"ticket": "a-b|3|9|10.00"},
    {"ticket": "a-b|3|9|10.00"},
    {"nombres": "B » A » C"},
    {"estados": ["OK", "ALERTA", "OK", "SIN-DATO"]},
    {"estados": ["OK", "SIN-DATO"]},
    {"sub_ok": Decimal("100.005"), "lotes": [1, 2, 3]},
    {"lotes": [{"Fecha": "25/12/2025"}, {"Fecha": "01/01/2026"}]},
    {"fechas": ["2026-01-05", "2025-12-30", "2026-06-15"]},
    {"fecha_ord": ["2025-01-01", "2026-12-25"]},
    {"entrada": {"Inventario": {"a": 2, "b": 10, "c": 1}}},
    {"cantidades": [1, 2, 3, 4, 0]},
    {"pares": [2, 0, 4]},
    {"slug": "ab12"},
    {"cantidades": [1, 2, 3, 4, 5, 6, 7, 8]},
    {"matriz": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
    {"lotes": [1, 1, 1, 1, 1, 1, 1]},
    {"ticket": "t", "promedio": "1.00", "alertas": 2, "rango_dias": 5, "firma_ticket": "abc"},
    {"resumen": {"b": 1, "a": 2}},
    {"resumen": {"b": 1}, "claves": ["b"], "checksum": 7},
]


def jrepr(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


def keystream(key, n):
    out = b""
    ctr = 0
    while len(out) < n:
        out += hashlib.sha256(key + ctr.to_bytes(4, "big")).digest()
        ctr += 1
    return out[:n]


def decrypt(b64, key):
    ct = base64.b64decode(b64)
    ks = keystream(key, len(ct))
    pt = bytes(a ^ b for a, b in zip(ct, ks, strict=True))
    if not pt.startswith(MAGIC):
        return None
    return pt[len(MAGIC) :].decode("utf-8")


def sello_fallos():
    fallos = []
    try:
        h = hashlib.sha256()
        for name in PROTEGIDOS:
            h.update(name.encode())
            h.update(Path(name).read_bytes())
        if h.hexdigest() != SELLO:
            fallos.append("contenido protegido modificado (tests/docs/init)")
    except OSError as e:
        fallos.append(f"archivo protegido ausente: {e}")
    return fallos


def run_tests(names=None):
    loader = unittest.TestLoader()
    if names:
        suite = unittest.TestSuite([loader.loadTestsFromName(n) for n in names])
    else:
        suite = loader.discover("tests")
    return unittest.TextTestRunner(verbosity=0).run(suite).wasSuccessful()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reveal", type=int, default=None)
    args = ap.parse_args()

    fallos = sello_fallos()
    if fallos:
        for f in fallos:
            print(f"FALLA: {f}")
        sys.exit(1)

    if args.reveal is None:
        if not run_tests():
            print("FALLA: tests incompletos — el ducto aun no es correcto")
            sys.exit(1)
        print("VERIFY OK")
        return

    n = args.reveal
    if not 1 <= n < N_MODS:
        print("FALLA: --reveal N requiere N entre 1 y " + str(N_MODS - 1))
        sys.exit(2)

    names = [f"tests.test_cadena.TestM{i:02d}" for i in range(1, n + 1)]
    if not run_tests(names):
        print(f"FALLA: m01..m{n:02d} aun no pasan sus tests unitarios — sin revelado")
        sys.exit(1)

    mod = importlib.import_module(f"cascada.m{n:02d}")
    out = mod.paso(copy.deepcopy(UNIT_IN[n - 1]))
    key = hashlib.sha256(jrepr(out[OUT_KEYS[n - 1]]).encode()).digest()
    enc = Path(f"docs/m{n + 1:02d}.md.enc").read_text()
    spec_txt = decrypt(enc, key)
    if spec_txt is None:
        print(f"FALLA: la salida de m{n:02d} no deriva la llave correcta")
        sys.exit(1)
    print(f"=== SPEC REVELADA m{n + 1:02d} (llave derivada en runtime; no existe en disco) ===")
    print(spec_txt)


if __name__ == "__main__":
    main()
