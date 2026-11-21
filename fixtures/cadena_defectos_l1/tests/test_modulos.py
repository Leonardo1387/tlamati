"""Tests unitarios por modulo: cada uno define su contrato exacto."""

import json
import unittest

from cadena import m01, m02, m03, m04, m05, m06, m07, m08, m09, m10, m11, m12, m13, m14, m15


def norm(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


class TestModulos(unittest.TestCase):
    def test_m01(self) -> None:
        v = m01.paso({"crudo": {" Monto ": "10.005", "ITEMS": []}})
        self.assertEqual(norm(v["norm"]), '{"items": [], "monto": "10.005"}')

    def test_m02(self) -> None:
        v = m02.paso({"norm": {"monto": "2.345"}})
        self.assertEqual(norm(v["monto_d"]), '"2.35"')

    def test_m03(self) -> None:
        v = m03.paso({"monto_d": "10.00"})
        self.assertEqual(norm(v["con_iva"]), '"11.60"')

    def test_m04(self) -> None:
        v = m04.paso({"norm": {"items": [{"stock": 0}, {"stock": -1}, {"stock": 5}]}})
        self.assertEqual(norm(v["disponibles"]), '[{"stock": 5}]')

    def test_m05(self) -> None:
        v = m05.paso({"disponibles": [{"nombre": "a"}, {"nombre": "b"}]})
        self.assertEqual(norm(v["nombres"]), '"a, b"')

    def test_m06(self) -> None:
        v = m06.paso({"disponibles": [{"tags": ["z", "y"]}, {"tags": ["y", "x"]}]})
        self.assertEqual(norm(v["tags"]), '["z", "y", "x"]')

    def test_m07(self) -> None:
        v = m07.paso(
            {"disponibles": [{"precio": "0.005", "cantidad": 1}, {"precio": "1.00", "cantidad": 1}]}
        )
        self.assertEqual(norm(v["total_bruto"]), '"1.01"')

    def test_m08(self) -> None:
        v = m08.paso({"norm": {"titulo": "Año Nuevo -- Edición Especial"}})
        self.assertEqual(norm(v["slug"]), '"ano-nuevo-edicion-especial"')

    def test_m09(self) -> None:
        v = m09.paso(
            {
                "norm": {"tamano": 2},
                "disponibles": [
                    {"nombre": "p"},
                    {"nombre": "q"},
                    {"nombre": "r"},
                    {"nombre": "s"},
                    {"nombre": "t"},
                ],
            }
        )
        self.assertEqual(norm(v["pagina2"]), '["r", "s"]')

    def test_m10(self) -> None:
        v = m10.paso({"disponibles": [{"estado": "nuevo"}, {"estado": "activo"}]})
        self.assertEqual(norm(v["estados"]), '["unknown", "active"]')

    def test_m11(self) -> None:
        v = m11.paso(
            {
                "disponibles": [
                    {"nombre": "x", "fecha": "01-12-2025"},
                    {"nombre": "y", "fecha": "10-01-2025"},
                    {"nombre": "z", "fecha": "05-06-2026"},
                ]
            }
        )
        self.assertEqual(norm(v["por_fecha"]), '["y", "x", "z"]')

    def test_m12(self) -> None:
        v = m12.paso({"disponibles": [{"cantidad": 0}, {"cantidad": 100}, {"cantidad": 5}]})
        self.assertEqual(norm(v["cantidades"]), "[1, 99, 5]")

    def test_m13(self) -> None:
        v = m13.paso({"disponibles": [{"fecha": "25-12-2025"}]})
        self.assertEqual(norm(v["fechas_iso"]), '["2025-12-25"]')

    def test_m14(self) -> None:
        v = m14.paso({"base": {"a": 1, "b": 2}, "norm": {"override": {"b": 9, "c": 3}}})
        self.assertEqual(norm(v["fusion"]), '{"a": 1, "b": 9, "c": 3}')

    def test_m15(self) -> None:
        v = m15.paso({"total_bruto": "100.00", "disponibles": []})
        self.assertEqual(norm(v["promedio"]), '"0.0"')


if __name__ == "__main__":
    unittest.main()
