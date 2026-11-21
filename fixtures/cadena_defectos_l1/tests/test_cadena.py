"""Tests de cadena completa con 2 semillas DISTINTAS a las unitarias
(anti-hardcode: los valores esperados solo cuadran con logica real)."""

import json
import unittest

import cadena


def norm(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


SEED_A = {
    "crudo": {
        "Monto": "1234.565",
        "Titulo": "Relación Anual de Café",
        "Tamano": 2,
        "Items": [
            {
                "nombre": "cafe",
                "stock": 3,
                "precio": "120.455",
                "cantidad": 2,
                "tags": ["b", "a"],
                "estado": "activo",
                "fecha": "03-01-2026",
            },
            {
                "nombre": "te",
                "stock": 0,
                "precio": "50.00",
                "cantidad": 120,
                "tags": ["a"],
                "estado": "agotado",
                "fecha": "01-02-2026",
            },
            {
                "nombre": "azucar",
                "stock": 7,
                "precio": "30.5",
                "cantidad": 0,
                "tags": ["c", "b", "a"],
                "estado": "reserva",
                "fecha": "15-12-2025",
            },
            {
                "nombre": "pan",
                "stock": 2,
                "precio": "15.125",
                "cantidad": 3,
                "tags": ["a", "c"],
                "estado": "nuevo",
                "fecha": "28-02-2026",
            },
        ],
        "Override": {"envio": 99, "monto": "0"},
    },
    "base": {"envio": 49, "moneda": "MXN"},
}

SEED_B = {
    "crudo": {
        "Monto": "99.995",
        "Titulo": "Órdenes de Año Nuevo",
        "Tamano": 3,
        "Items": [
            {
                "nombre": "miel",
                "stock": 1,
                "precio": "85.255",
                "cantidad": 4,
                "tags": ["z", "y"],
                "estado": "reserva",
                "fecha": "30-06-2026",
            },
            {
                "nombre": "atun",
                "stock": 0,
                "precio": "22.00",
                "cantidad": 1,
                "tags": ["y"],
                "estado": "agotado",
                "fecha": "02-02-2026",
            },
            {
                "nombre": "arroz",
                "stock": 12,
                "precio": "18.005",
                "cantidad": 150,
                "tags": ["x", "z"],
                "estado": "activo",
                "fecha": "11-11-2025",
            },
        ],
        "Override": {"moneda": "USD"},
    },
    "base": {"envio": 10, "moneda": "MXN", "extra": True},
}


class TestCadena(unittest.TestCase):
    def test_cadena_a(self) -> None:
        out = cadena.ejecutar(json.loads(json.dumps(SEED_A, default=str)))

        self.assertEqual(norm(out["monto_d"]), '"1234.57"')
        self.assertEqual(norm(out["con_iva"]), '"1432.10"')
        self.assertEqual(norm(out["nombres"]), '"cafe, azucar, pan"')
        self.assertEqual(norm(out["tags"]), '["b", "a", "c"]')
        self.assertEqual(norm(out["total_bruto"]), '"286.29"')
        self.assertEqual(norm(out["slug"]), '"relacion-anual-de-cafe"')
        self.assertEqual(norm(out["pagina2"]), '["pan"]')
        self.assertEqual(norm(out["estados"]), '["active", "backorder", "unknown"]')
        self.assertEqual(norm(out["por_fecha"]), '["azucar", "cafe", "pan"]')
        self.assertEqual(norm(out["cantidades"]), "[2, 1, 3]")
        self.assertEqual(norm(out["fechas_iso"]), '["2026-01-03", "2025-12-15", "2026-02-28"]')
        self.assertEqual(norm(out["fusion"]), '{"envio": 99, "moneda": "MXN", "monto": "0"}')
        self.assertEqual(norm(out["promedio"]), '"95.4"')

    def test_cadena_b(self) -> None:
        out = cadena.ejecutar(json.loads(json.dumps(SEED_B, default=str)))

        self.assertEqual(norm(out["monto_d"]), '"100.00"')
        self.assertEqual(norm(out["con_iva"]), '"116.00"')
        self.assertEqual(norm(out["nombres"]), '"miel, arroz"')
        self.assertEqual(norm(out["tags"]), '["z", "y", "x"]')
        self.assertEqual(norm(out["total_bruto"]), '"3041.77"')
        self.assertEqual(norm(out["slug"]), '"ordenes-de-ano-nuevo"')
        self.assertEqual(norm(out["pagina2"]), "[]")
        self.assertEqual(norm(out["estados"]), '["backorder", "active"]')
        self.assertEqual(norm(out["por_fecha"]), '["arroz", "miel"]')
        self.assertEqual(norm(out["cantidades"]), "[4, 99]")
        self.assertEqual(norm(out["fechas_iso"]), '["2026-06-30", "2025-11-11"]')
        self.assertEqual(norm(out["fusion"]), '{"envio": 10, "extra": true, "moneda": "USD"}')
        self.assertEqual(norm(out["promedio"]), '"1520.9"')


if __name__ == "__main__":
    unittest.main()
