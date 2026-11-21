"""Tests de cadena completa con 2 semillas DISTINTAS a las unitarias
(anti-hardcode: los valores esperados solo cuadran con logica real)."""

# ruff: noqa: E501

import json
import unittest

import ducto


def norm(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


SEED_A = {
    "crudo2": {
        "Texto": "El Águila, el águila y el Sol; sol.",
        "Numeros": ["1.005", "2.345", "0.1"],
        "Lista": [1, 2, 3, 4, 5, 6, 7, 8],
        "Registro": {" Monto ": "250.005", "Activo": "si", " DESC ": "10", "Check": "07"},
        "Fechas": ["2026/12/25", "2025/01/01", "2026/06/15"],
        "Mapa": {"a": 1, "b": 2, "c": 1},
        "Codigo": "MX_2026-x9!",
        "Frases": ["  Desarrollo de Software ", "Pruebas Unitarias", " Entrega Final  "],
    }
}

SEED_B = {
    "crudo2": {
        "Texto": "la Lluvia en Sevilla, es un prodigio; la lluvia.",
        "Numeros": ["9.995", "0.001", "12.5"],
        "Lista": [10, 15, 20, 25, 30, 31, 32],
        "Registro": {"monto": "99.995", "activo": "no", "desc": "5", "check": "7"},
        "Fechas": ["2024/02/29", "2026/01/01"],
        "Mapa": {"x": "k", "y": "k", "z": "j"},
        "Codigo": "ab-12_CD#",
        "Frases": ["Uno ", " Dos", "Tres"],
    }
}


class TestCadena(unittest.TestCase):
    def test_cadena_a(self) -> None:
        out = ducto.ejecutar(json.loads(json.dumps(SEED_A, default=str)))

        self.assertEqual(norm(out["suma"]), '"3.46"')
        self.assertEqual(norm(out["top3"]), '[["el", 3], ["sol", 2], ["águila", 2]]')
        self.assertEqual(norm(out["con_desc"]), '"225.01"')
        self.assertEqual(norm(out["rango"]), "723")
        self.assertEqual(norm(out["checksum"]), "10")
        self.assertEqual(norm(out["valido"]), "false")
        self.assertEqual(norm(out["paginas"]), "2")
        self.assertEqual(norm(out["firma"]), '"4de9d54c9a605c62"')
        self.assertEqual(
            norm(out["salida"]),
            '{"claves": ["activo", "paginas", "total", "valido"], "firma": "4de9d54c9a605c62", "resumen": {"activo": true, "paginas": 2, "total": "3.46", "valido": false}}',
        )

    def test_cadena_b(self) -> None:
        out = ducto.ejecutar(json.loads(json.dumps(SEED_B, default=str)))

        self.assertEqual(norm(out["suma"]), '"22.50"')
        self.assertEqual(norm(out["top3"]), '[["la", 2], ["lluvia", 2], ["en", 1]]')
        self.assertEqual(norm(out["con_desc"]), '"95.00"')
        self.assertEqual(norm(out["rango"]), "672")
        self.assertEqual(norm(out["checksum"]), "26")
        self.assertEqual(norm(out["valido"]), "false")
        self.assertEqual(norm(out["paginas"]), "2")
        self.assertEqual(norm(out["firma"]), '"3c36843d111cb5f9"')
        self.assertEqual(
            norm(out["salida"]),
            '{"claves": ["activo", "paginas", "total", "valido"], "firma": "3c36843d111cb5f9", "resumen": {"activo": false, "paginas": 2, "total": "22.50", "valido": false}}',
        )


if __name__ == "__main__":
    unittest.main()
