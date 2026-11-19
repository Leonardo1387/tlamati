import unittest

from app.moneda import formatear, simbolo


class TestMoneda(unittest.TestCase):
    def test_simbolo_mx(self):
        self.assertEqual(simbolo(), "$")

    def test_formatear_monto(self):
        self.assertEqual(formatear(1234.5), "$1,234.50")
