import unittest

from texto.procesar import dividir_csv, normalizar_espacios, slugify, truncar


class TestDividirCsv(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(dividir_csv("a,b,c"), ["a", "b", "c"])

    def test_espacios(self):
        self.assertEqual(dividir_csv(" a , b "), ["a", "b"])

    def test_comillas(self):
        self.assertEqual(dividir_csv('a,"b,c",d'), ["a", "b,c", "d"])

    def test_vacio(self):
        self.assertEqual(dividir_csv(""), [""])


class TestSlugify(unittest.TestCase):
    def test_basico(self):
        self.assertEqual(slugify("Hola Mundo"), "hola-mundo")

    def test_acentos(self):
        self.assertEqual(slugify("Café Niño"), "cafe-nino")


class TestTruncar(unittest.TestCase):
    def test_corte(self):
        self.assertEqual(truncar("abcdefgh", 5), "abcde…")

    def test_sin_corte(self):
        self.assertEqual(truncar("abc", 5), "abc")


class TestNormalizar(unittest.TestCase):
    def test_espacios(self):
        self.assertEqual(normalizar_espacios("a  b"), "a b")

    def test_tabs(self):
        self.assertEqual(normalizar_espacios("a\tb  c"), "a b c")
