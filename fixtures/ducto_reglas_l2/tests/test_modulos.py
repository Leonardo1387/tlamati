"""Tests unitarios por modulo: cada uno define su contrato exacto."""

import json
import unittest

from ducto import (
    s01,
    s02,
    s03,
    s04,
    s05,
    s06,
    s07,
    s08,
    s09,
    s10,
    s11,
    s12,
    s13,
    s14,
    s15,
    s16,
    s17,
    s18,
    s19,
    s20,
    s21,
    s22,
    s23,
    s24,
    s25,
    s26,
    s27,
    s28,
    s29,
    s30,
)


def norm(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


class TestModulos(unittest.TestCase):
    def test_s01_r_01(self) -> None:
        v = s01.paso({"crudo2": {"Texto": "El Águila, el águila; y el sol."}})
        self.assertEqual(norm(v["palabras"]), '["el", "águila", "el", "águila", "y", "el", "sol"]')

    def test_s02_r_02(self) -> None:
        v = s02.paso({"palabras": ["b", "a", "b", "c", "a"]})
        self.assertEqual(norm(v["unicas"]), '["b", "a", "c"]')

    def test_s03_r_03(self) -> None:
        v = s03.paso({"palabras": ["x", "y", "x"], "unicas": ["x", "y"]})
        self.assertEqual(norm(v["contador"]), '{"x": 2, "y": 1}')

    def test_s04_r_04(self) -> None:
        v = s04.paso({"contador": {"a": 2, "b": 3, "c": 3, "d": 1}})
        self.assertEqual(norm(v["top3"]), '[["b", 3], ["c", 3], ["a", 2]]')

    def test_s05_r_05(self) -> None:
        v = s05.paso({"top3": [["sol", 3], ["el", 2], ["águila", 1]]})
        self.assertEqual(norm(v["iniciales"]), '"S.E.Á"')

    def test_s06_r_06(self) -> None:
        v = s06.paso({"crudo2": {"Registro": {" Monto ": "1", "ACTIVO": "si"}}})
        self.assertEqual(norm(v["registro"]), '{"activo": "si", "monto": "1"}')

    def test_s07_r_07(self) -> None:
        v = s07.paso({"registro": {"activo": "no"}})
        self.assertEqual(norm(v["activo"]), "false")

    def test_s08_r_08(self) -> None:
        v = s08.paso({"registro": {"monto": "2.345"}})
        self.assertEqual(norm(v["monto2"]), '"2.35"')

    def test_s09_r_09(self) -> None:
        v = s09.paso({"registro": {"monto": "200.00", "desc": "10"}, "monto2": "200.00"})
        self.assertEqual(norm(v["con_desc"]), '"180.00"')

    def test_s10_r_10(self) -> None:
        v = s10.paso({"crudo2": {"Fechas": ["2026/12/25", "2025/01/01", "2026/06/15"]}})
        self.assertEqual(norm(v["fechas2"]), '["2025-01-01", "2026-06-15", "2026-12-25"]')

    def test_s11_r_11(self) -> None:
        v = s11.paso({"fechas2": ["2025-01-01", "2026-12-25"]})
        self.assertEqual(norm(v["rango"]), "723")

    def test_s12_r_12(self) -> None:
        v = s12.paso({"crudo2": {"Mapa": {"a": 1, "b": 2, "c": 1}}})
        self.assertEqual(norm(v["mapa_inv"]), '{"1": "a", "2": "b"}')

    def test_s13_r_13(self) -> None:
        v = s13.paso({"crudo2": {"Codigo": "MX_2026-x9!"}})
        self.assertEqual(norm(v["codigo"]), '"MX2026X9"')

    def test_s14_r_14(self) -> None:
        v = s14.paso({"codigo": "AB12"})
        self.assertEqual(norm(v["checksum"]), "59")

    def test_s15_r_15(self) -> None:
        v = s15.paso({"checksum": 7, "registro": {"check": "07"}})
        self.assertEqual(norm(v["valido"]), "true")

    def test_s16_r_16(self) -> None:
        v = s16.paso({"crudo2": {"Numeros": ["1.005", "2.345", "0.1"]}})
        self.assertEqual(norm(v["numeros"]), '["1.01", "2.35", "0.10"]')

    def test_s17_r_17(self) -> None:
        v = s17.paso({"numeros": ["0.10", "0.20"]})
        self.assertEqual(norm(v["suma"]), '"0.30"')

    def test_s18_r_18(self) -> None:
        v = s18.paso({"crudo2": {"Lista": [1, 2, 3, 4, 5, 6]}})
        self.assertEqual(norm(v["pares"]), "[2, 4, 6]")

    def test_s19_r_19(self) -> None:
        v = s19.paso({"pares": [2, 0, 4]})
        self.assertEqual(norm(v["producto"]), "8")

    def test_s20_r_20(self) -> None:
        v = s20.paso({"crudo2": {"Texto": "hola Mundo"}})
        self.assertEqual(norm(v["mayus"]), '"HOLA MUNDO"')

    def test_s21_r_21(self) -> None:
        v = s21.paso(
            {
                "crudo2": {
                    "Frases": ["  Desarrollo de Software ", "Pruebas Unitarias", " Entrega Final  "]
                }
            }
        )
        self.assertEqual(
            norm(v["frase"]), '"Desarrollo de Software | Pruebas Unitarias | Entrega Final"'
        )

    def test_s22_r_22(self) -> None:
        v = s22.paso({"frase": "Desarrollo | Pruebas"})
        self.assertEqual(norm(v["acronimo"]), '"DP"')

    def test_s23_r_23(self) -> None:
        v = s23.paso({"palabras": ["a", "b", "c", "d", "e", "f", "g"]})
        self.assertEqual(norm(v["paginas"]), "2")

    def test_s24_r_24(self) -> None:
        v = s24.paso({"crudo2": {"Lista": [1, 2, 3, 4, 5, 6, 7, 8]}})
        self.assertEqual(norm(v["matriz"]), "[[1, 2, 3], [4, 5, 6], [7, 8, 0]]")

    def test_s25_r_25(self) -> None:
        v = s25.paso({"matriz": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
        self.assertEqual(norm(v["traspuesta"]), "[[1, 4, 7], [2, 5, 8], [3, 6, 9]]")

    def test_s26_r_26(self) -> None:
        v = s26.paso({"matriz": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
        self.assertEqual(norm(v["diagonal"]), "[1, 5, 9]")

    def test_s27_r_27(self) -> None:
        v = s27.paso({"suma": "10.50", "checksum": 42})
        self.assertEqual(norm(v["firma"]), '"ddb294c0afd630dc"')

    def test_s28_r_28(self) -> None:
        v = s28.paso({"suma": "10.50", "activo": True, "valido": False, "paginas": 3})
        self.assertEqual(
            norm(v["resumen"]), '{"activo": true, "paginas": 3, "total": "10.50", "valido": false}'
        )

    def test_s29_r_29(self) -> None:
        v = s29.paso({"resumen": {"b": 1, "a": 2}})
        self.assertEqual(norm(v["claves"]), '["a", "b"]')

    def test_s30_r_30(self) -> None:
        v = s30.paso({"resumen": {"b": 1}, "firma": "f", "claves": ["b"]})
        self.assertEqual(norm(v["salida"]), '{"claves": ["b"], "firma": "f", "resumen": {"b": 1}}')


if __name__ == "__main__":
    unittest.main()
