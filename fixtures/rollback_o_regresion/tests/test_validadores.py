import unittest

from validadores import (
    validar_cp,
    validar_curp,
    validar_email,
    validar_fecha,
    validar_rfc,
    validar_telefono,
)


class TestValidadores(unittest.TestCase):
    def test_email(self):
        self.assertTrue(validar_email("ana@mail.example.com"))
        self.assertTrue(validar_email("simple@dominio.mx"))
        self.assertFalse(validar_email("sin-arroba"))

    def test_telefono(self):
        self.assertTrue(validar_telefono("5512345678"))
        self.assertFalse(validar_telefono("551234567"))

    def test_cp(self):
        self.assertTrue(validar_cp("03100"))
        self.assertFalse(validar_cp("0310"))

    def test_rfc(self):
        self.assertTrue(validar_rfc("XAXX010101000"))
        self.assertFalse(validar_rfc("xaxx010101000"))

    def test_curp(self):
        self.assertTrue(validar_curp("GARC850101HDFRRL09"))
        self.assertFalse(validar_curp("CORTA"))

    def test_fecha(self):
        self.assertTrue(validar_fecha("2026-11-19"))
        self.assertFalse(validar_fecha("19-11-2026"))
        self.assertFalse(validar_fecha("2026-13-01"))
