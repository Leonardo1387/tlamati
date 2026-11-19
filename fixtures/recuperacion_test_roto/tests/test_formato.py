import unittest

from app.formato import fecha, telefono


class TestFormato(unittest.TestCase):
    def test_telefono_mx(self):
        self.assertEqual(telefono("5512345678"), "(551) 2345-678")

    def test_fecha_mx(self):
        self.assertEqual(fecha(5, 3, 2026), "05/03/2026")

    def test_telefono_invalido(self):
        with self.assertRaises(ValueError):
            telefono("123")
