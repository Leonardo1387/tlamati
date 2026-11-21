"""Tests unitarios + cadena con HASHES del output esperado (los literales
no viven en disco: la unica forma de pasarlos es implementar cada contrato
correctamente; las specs se revelan con verify.py --reveal N)."""

import hashlib
import json
import unittest
from decimal import Decimal

import cascada
from cascada import (
    m01,
    m02,
    m03,
    m04,
    m05,
    m06,
    m07,
    m08,
    m09,
    m10,
    m11,
    m12,
    m13,
    m14,
    m15,
    m16,
    m17,
    m18,
    m19,
    m20,
    m21,
    m22,
    m23,
    m24,
    m25,
    m26,
    m27,
    m28,
    m29,
    m30,
    m31,
    m32,
    m33,
    m34,
)


def norm(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


def h(x):
    return hashlib.sha256(norm(x).encode()).hexdigest()


class TestM01(unittest.TestCase):
    def test_m01(self):
        u = {"entrada": {"Lotes": [{"ID": "a"}, {"ID": "b"}]}}
        out = m01.paso(u)
        self.assertEqual(
            h(out["lotes"]), "6b7a2cacbede0c88c2ef39fe754a438ed41a77f962998aa497fe5eef8ed1ff93"
        )


class TestM02(unittest.TestCase):
    def test_m02(self):
        u = {"lotes": [{"ID": "MX#N#1"}, {"ID": "MX#S#2"}, {"ID": "MX#O#3"}]}
        out = m02.paso(u)
        self.assertEqual(
            h(out["ids"]), "9d2806d516b63cb8182efba653b350c44f67213f5a5791b71956d3414995aacc"
        )


class TestM03(unittest.TestCase):
    def test_m03(self):
        u = {"lotes": [{"Cantidad": " 12 "}, {"Cantidad": "-3"}, {"Cantidad": "0"}]}
        out = m03.paso(u)
        self.assertEqual(
            h(out["cantidades"]), "fcb4d2c105652803f346fd838b9bf8d692912ac0d9922b3bf7cc5d8f5d8da62b"
        )


class TestM04(unittest.TestCase):
    def test_m04(self):
        u = {"cantidades": [3, -2, 7]}
        out = m04.paso(u)
        self.assertEqual(
            h(out["suma_cant"]), "2c624232cdd221771294dfbb310aca000a0df6ac8b66b696d90ef06fdefb64a3"
        )


class TestM05(unittest.TestCase):
    def test_m05(self):
        u = {"entrada": {"Ruta": "Almacén Norte — Sección 7"}}
        out = m05.paso(u)
        self.assertEqual(
            h(out["slug"]), "1563f79271a008ffa951a27184c79465f17b01abda791ff983302be8b35685b2"
        )


class TestM06(unittest.TestCase):
    def test_m06(self):
        u = {"slug": "x7-12-y3-z"}
        out = m06.paso(u)
        self.assertEqual(
            h(out["slug_inverso"]),
            "1d67ec2f05bf30725a2a12adecab035adeaae827ff765c22bcc894b7cb29b7d0",
        )


class TestM07(unittest.TestCase):
    def test_m07(self):
        u = {"lotes": [{"Estado": "lleno"}, {"Estado": "vacío"}, {"Estado": "??"}]}
        out = m07.paso(u)
        self.assertEqual(
            h(out["estados"]), "cafe26a62ac7fb96fb71fca84b60f17a853107507e8228d948be0bf8ddff82f5"
        )


class TestM08(unittest.TestCase):
    def test_m08(self):
        u = {"lotes": [{"Lote": "café"}, {"Lote": "té"}]}
        out = m08.paso(u)
        self.assertEqual(
            h(out["nombres"]), "992d2b8d79ccf0aed52f3791f8f9969100633adfa7db096dc68870368e076087"
        )


class TestM09(unittest.TestCase):
    def test_m09(self):
        u = {"lotes": [{"Precio": "0.005"}, {"Precio": "10.004"}], "cantidades": [3, 1]}
        out = m09.paso(u)
        self.assertEqual(
            h(out["subtotal"]), "4fa8e18da85ae482d030333457da7467bc45e4f3eccfea04b1a80d27056bb5dd"
        )


class TestM10(unittest.TestCase):
    def test_m10(self):
        u = {"entrada": {"Salida": "100.005"}, "subtotal": "30.01"}
        out = m10.paso(u)
        self.assertEqual(
            h(out["saldo"]), "523d70e5f262d41021e665a3706931584cbb334f80d5968f7a3a220140b3549b"
        )


class TestM11(unittest.TestCase):
    def test_m11(self):
        u = {"subtotal": "12.34"}
        out = m11.paso(u)
        self.assertEqual(
            h(out["sub_ok"]), "558a2ada104694954845416225fb93f2b2e378b03f35412e59cf60a3e57952c8"
        )


class TestM12(unittest.TestCase):
    def test_m12(self):
        u = {"entrada": {"Inventario": {"a": 1, "b": 2, "c": 1}}}
        out = m12.paso(u)
        self.assertEqual(
            h(out["mapa_inv"]), "47bf474b90f62e12d73be5eaa50e31d9310e9cc38b1b03fa8285feeccc4b40b3"
        )


class TestM13(unittest.TestCase):
    def test_m13(self):
        u = {"ids": [("x#y#1", 1), ("x#y#2", 2), ("x#y#1", 1)], "cantidades": [5, 3, 7]}
        out = m13.paso(u)
        self.assertEqual(
            h(out["por_zona"]), "cacb0a8aeba1fe299fe2f08225f3357929311f881763992ab42c9fe8e1cacbc1"
        )


class TestM14(unittest.TestCase):
    def test_m14(self):
        u = {"por_zona": {1: 9, 2: 9, 3: 4}}
        out = m14.paso(u)
        self.assertEqual(
            h(out["zona_max"]), "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b"
        )


class TestM15(unittest.TestCase):
    def test_m15(self):
        u = {"slug": "a-b", "lotes": [1, 2, 3], "suma_cant": 9, "subtotal": "10.00"}
        out = m15.paso(u)
        self.assertEqual(
            h(out["ticket"]), "1dc2a4537267b9434b69c32730d20fde549355e3f78731dcdb9495e2d380696a"
        )


class TestM16(unittest.TestCase):
    def test_m16(self):
        u = {"ticket": "a-b|3|9|10.00"}
        out = m16.paso(u)
        self.assertEqual(
            h(out["ticket_ok"]), "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
        )


class TestM17(unittest.TestCase):
    def test_m17(self):
        u = {"ticket": "a-b|3|9|10.00"}
        out = m17.paso(u)
        self.assertEqual(
            h(out["firma_ticket"]),
            "a7e35cff23e51036b6f91cc94183d6d32b249d5a2581a411e5ee4cc9a1cb0ec9",
        )


class TestM18(unittest.TestCase):
    def test_m18(self):
        u = {"nombres": "B » A » C"}
        out = m18.paso(u)
        self.assertEqual(
            h(out["orden_alf"]), "3143395fc69a863549e3b04b329f6a1474bede15a483fa11c8aa32d79cc79831"
        )


class TestM19(unittest.TestCase):
    def test_m19(self):
        u = {"estados": ["OK", "ALERTA", "OK", "SIN-DATO"]}
        out = m19.paso(u)
        self.assertEqual(
            h(out["estados_uni"]),
            "cafe26a62ac7fb96fb71fca84b60f17a853107507e8228d948be0bf8ddff82f5",
        )


class TestM20(unittest.TestCase):
    def test_m20(self):
        u = {"estados": ["OK", "SIN-DATO"]}
        out = m20.paso(u)
        self.assertEqual(
            h(out["flag_alerta"]),
            "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        )


class TestM21(unittest.TestCase):
    def test_m21(self):
        u = {"sub_ok": Decimal("100.005"), "lotes": [1, 2, 3]}
        out = m21.paso(u)
        self.assertEqual(
            h(out["promedio"]), "11b5c2e8a51d0efbdb414b1028df45f1eaee1ab8e83e5046fdc1c997b5ea98f5"
        )


class TestM22(unittest.TestCase):
    def test_m22(self):
        u = {"lotes": [{"Fecha": "25/12/2025"}, {"Fecha": "01/01/2026"}]}
        out = m22.paso(u)
        self.assertEqual(
            h(out["fechas"]), "e4b6ee0b701ae30b694c5dc0e4a11e5764cd61dee7b514ff8c94a8c21edf2bea"
        )


class TestM23(unittest.TestCase):
    def test_m23(self):
        u = {"fechas": ["2026-01-05", "2025-12-30", "2026-06-15"]}
        out = m23.paso(u)
        self.assertEqual(
            h(out["fecha_ord"]), "849cb5de2227e27ed5a63487a6057e131662a71a228aa1110b71bf72c5d8f95c"
        )


class TestM24(unittest.TestCase):
    def test_m24(self):
        u = {"fecha_ord": ["2025-01-01", "2026-12-25"]}
        out = m24.paso(u)
        self.assertEqual(
            h(out["rango_dias"]), "07e46896ba89f88776fed50a1b7895129f9b9af7d3b8b33ca23af478bb818d6c"
        )


class TestM25(unittest.TestCase):
    def test_m25(self):
        u = {"entrada": {"Inventario": {"a": 2, "b": 10, "c": 1}}}
        out = m25.paso(u)
        self.assertEqual(
            h(out["inventario_plano"]),
            "963fe983b74aab2b59c1a693c4ac5eefc2e3d9b6800ae320d6972487d4fdec3b",
        )


class TestM26(unittest.TestCase):
    def test_m26(self):
        u = {"cantidades": [1, 2, 3, 4, 0]}
        out = m26.paso(u)
        self.assertEqual(
            h(out["pares"]), "a39b2bbd7e33fd38003005cf7be4bf45a4243bb2eec7f17c5d2d15b675be9ee0"
        )


class TestM27(unittest.TestCase):
    def test_m27(self):
        u = {"pares": [2, 0, 4]}
        out = m27.paso(u)
        self.assertEqual(
            h(out["producto_pares"]),
            "2c624232cdd221771294dfbb310aca000a0df6ac8b66b696d90ef06fdefb64a3",
        )


class TestM28(unittest.TestCase):
    def test_m28(self):
        u = {"slug": "ab12"}
        out = m28.paso(u)
        self.assertEqual(
            h(out["checksum"]), "6208ef0f7750c111548cf90b6ea1d0d0a66f6bff40dbef07cb45ec436263c7d6"
        )


class TestM29(unittest.TestCase):
    def test_m29(self):
        u = {"cantidades": [1, 2, 3, 4, 5, 6, 7, 8]}
        out = m29.paso(u)
        self.assertEqual(
            h(out["matriz"]), "879d0bb8a6a50e11a2108e6ad07426e581cf23dd25b189f8609f126b1cad2c0b"
        )


class TestM30(unittest.TestCase):
    def test_m30(self):
        u = {"matriz": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]}
        out = m30.paso(u)
        self.assertEqual(
            h(out["traspuesta"]), "e44c19e716fa5f642713e7f21af1f44a41597c4b038c26deaf9c9203de1d5fe9"
        )


class TestM31(unittest.TestCase):
    def test_m31(self):
        u = {"lotes": [1, 1, 1, 1, 1, 1, 1]}
        out = m31.paso(u)
        self.assertEqual(
            h(out["paginas"]), "d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35"
        )


class TestM32(unittest.TestCase):
    def test_m32(self):
        u = {
            "ticket": "t",
            "promedio": "1.00",
            "alertas": 2,
            "rango_dias": 5,
            "firma_ticket": "abc",
        }
        out = m32.paso(u)
        self.assertEqual(
            h(out["resumen"]), "91a3e0ee04c1d196f55bee0cded00a3dbe9aaf7240d904dd648295aa873e8456"
        )


class TestM33(unittest.TestCase):
    def test_m33(self):
        u = {"resumen": {"b": 1, "a": 2}}
        out = m33.paso(u)
        self.assertEqual(
            h(out["claves"]), "3554d2b8a1e34099053865de8576d1460b807430ec8c6b85315c9607ba93d308"
        )


class TestM34(unittest.TestCase):
    def test_m34(self):
        u = {"resumen": {"b": 1}, "claves": ["b"], "checksum": 7}
        out = m34.paso(u)
        self.assertEqual(
            h(out["salida"]), "f832e937fea8604ac153f01ce9d167ce7b5fe0a38a6f3cafdebd9f2fa40d3760"
        )


SEED_A = {
    "entrada": {
        "Ruta": "Almacén Norte — Sección 7",
        "Salida": "9999.995",
        "Inventario": {"bodega": "A1", "patio": "B2", "techo": "A1"},
        "Lotes": [
            {
                "ID": "MX#NTE#3",
                "Lote": "café grano",
                "Cantidad": " 12 ",
                "Precio": "120.455",
                "Estado": "lleno",
                "Fecha": "03/01/2026",
            },
            {
                "ID": "MX#SUR#1",
                "Lote": "té verde",
                "Cantidad": "7",
                "Precio": "50.00",
                "Estado": "vacío",
                "Fecha": "01/02/2026",
            },
            {
                "ID": "MX#NTE#3",
                "Lote": "azúcar",
                "Cantidad": "0",
                "Precio": "30.5",
                "Estado": "medio",
                "Fecha": "15/12/2025",
            },
            {
                "ID": "MX#OES#2",
                "Lote": "panela",
                "Cantidad": "5",
                "Precio": "15.125",
                "Estado": "roto",
                "Fecha": "28/02/2026",
            },
            {
                "ID": "MX#SUR#1",
                "Lote": "miel",
                "Cantidad": "3",
                "Precio": "85.255",
                "Estado": "lleno",
                "Fecha": "30/06/2026",
            },
            {
                "ID": "MX#OES#2",
                "Lote": "sal",
                "Cantidad": "21",
                "Precio": "9.995",
                "Estado": "vacío",
                "Fecha": "11/11/2025",
            },
        ],
    }
}


class TestCadenaA(unittest.TestCase):
    def test_cadena_a_completa(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["salida"]), "c4ed91bff26bea8dd25f94c14d8fb3618706f49bdf0c2c47701b6c0af013cb72"
        )

    def test_cadena_a_subtotal(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["subtotal"]), "ebce98c6ee8010f456a8b0a4d4458cf608f529c4c40104a3b8b21591f55c0dbd"
        )

    def test_cadena_a_saldo(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["saldo"]), "b2a7cc91276762dc1281ee4eddf1da53d777f6622c26c6987f2cdb928adb0eed"
        )

    def test_cadena_a_ticket(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["ticket"]), "1f0081c596d7e5a1d06058b656fd96d400d5ea4f505146d51ba72859ba2d257b"
        )

    def test_cadena_a_firma_ticket(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["firma_ticket"]),
            "3902bbf6d6ee8a380fb39d202250345a8c74439e8f7a3f4b72bf6d790a18fc82",
        )

    def test_cadena_a_promedio(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["promedio"]), "c3187f7a80db403aad01ca54f6323dc054be5e5bcaae9a61c64d6caf40e6dc3c"
        )

    def test_cadena_a_rango_dias(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["rango_dias"]), "138d9e809e386a7b800791d1f664f56d1c55f3d1ba411b950862729bc486c5ce"
        )

    def test_cadena_a_checksum(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["checksum"]), "535fa30d7e25dd8a49f1536779734ec8286108d115da5045d77f3b4185d8f790"
        )

    def test_cadena_a_salida(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["salida"]), "c4ed91bff26bea8dd25f94c14d8fb3618706f49bdf0c2c47701b6c0af013cb72"
        )

    def test_cadena_a_nombres(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["nombres"]), "f4c718cebcb0e070ea456a023cdf3d7718e2fa48a8aa395e7af7a8b396681ebe"
        )

    def test_cadena_a_orden_alf(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["orden_alf"]), "073cd099d08d7c038a975bf385f01a3b7a9df09e9a7292afd3da25ccf556e86c"
        )

    def test_cadena_a_por_zona(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["por_zona"]), "e6720617b80e9abc821291243fc15a70bad3f821bc1730fc68f5ba46eb17674d"
        )

    def test_cadena_a_zona_max(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["zona_max"]), "d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35"
        )

    def test_cadena_a_matriz(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["matriz"]), "dc337e096992b3fa859540de6a26633013d990b5f6e67270be56868649a99c10"
        )

    def test_cadena_a_traspuesta(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["traspuesta"]), "1bb96fd80e0a3a1be2872a7c5713840806d2fb04dfb6b26263767aec176bb754"
        )

    def test_cadena_a_resumen(self):
        out = cascada.ejecutar(json.loads(norm(SEED_A)))
        self.assertEqual(
            h(out["resumen"]), "9ba6a8f002270b420548a145922f4d3471da7fa032e11bd8c842d86a08b644d0"
        )


SEED_B = {
    "entrada": {
        "Ruta": "Bodega Órdenes Año Nuevo",
        "Salida": "500.00",
        "Inventario": {"norte": "Z9", "sur": "Z1", "este": "Z9"},
        "Lotes": [
            {
                "ID": "VT#A#10",
                "Lote": "arroz",
                "Cantidad": "150",
                "Precio": "18.005",
                "Estado": "lleno",
                "Fecha": "11/11/2025",
            },
            {
                "ID": "VT#B#4",
                "Lote": "atún",
                "Cantidad": "1",
                "Precio": "22.00",
                "Estado": "agotado",
                "Fecha": "02/02/2026",
            },
            {
                "ID": "VT#A#10",
                "Lote": "frijol",
                "Cantidad": "8",
                "Precio": "41.005",
                "Estado": "medio",
                "Fecha": "29/02/2024",
            },
        ],
    }
}


class TestCadenaB(unittest.TestCase):
    def test_cadena_b_completa(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["salida"]), "9af3c398dfa9f17ea871f185844cb52758d1003f8f62e8e98db1355eac87eb9b"
        )

    def test_cadena_b_subtotal(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["subtotal"]), "ce3160323dfa88eefc091e4807a1b8e304ac8e344210bb8ebbb3464551adbbd5"
        )

    def test_cadena_b_saldo(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["saldo"]), "9336b19ea628ad0939f712acedfa17bd9c44ed6c13a39b6ea21edffab4aa59be"
        )

    def test_cadena_b_ticket(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["ticket"]), "07841ab721fda918cf0c33b1bb743f33bbdc51da88fa5869f1d1cec569bd0e52"
        )

    def test_cadena_b_firma_ticket(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["firma_ticket"]),
            "bea81c167e8431dcfd7d638ee1e5969e013a23beefdaa14ed2c0ef71a6c365ce",
        )

    def test_cadena_b_promedio(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["promedio"]), "7389d73a80e6840a70846b5a901ea0c563c4d616f056e50af7dcff40778eaed1"
        )

    def test_cadena_b_rango_dias(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["rango_dias"]), "e4e549408422875958476160732390defefcac7c2bd8353d918fe452d20de2a6"
        )

    def test_cadena_b_checksum(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["checksum"]), "9f14025af0065b30e47e23ebb3b491d39ae8ed17d33739e5ff3827ffb3634953"
        )

    def test_cadena_b_salida(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["salida"]), "9af3c398dfa9f17ea871f185844cb52758d1003f8f62e8e98db1355eac87eb9b"
        )

    def test_cadena_b_nombres(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["nombres"]), "d538a7089ea0a0725e5ae62da82d77078d11d874e6596ad5996dd4036895d78e"
        )

    def test_cadena_b_orden_alf(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["orden_alf"]), "d538a7089ea0a0725e5ae62da82d77078d11d874e6596ad5996dd4036895d78e"
        )

    def test_cadena_b_por_zona(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["por_zona"]), "fc83372e45617dfd09f673b535cfd1f710e41e008341dea1abb3281961cab5bb"
        )

    def test_cadena_b_zona_max(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["zona_max"]), "4a44dc15364204a80fe80e9039455cc1608281820fe2b24f1e5233ade6af1dd5"
        )

    def test_cadena_b_matriz(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["matriz"]), "054892ec534724f2a3112db90781ae0970a4fb56e49e8306a7a1ee1eac3fb6cf"
        )

    def test_cadena_b_traspuesta(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["traspuesta"]), "3c82a642ce7e77e319f2dd0f8e513ea3de6573018ed38bc6efae773c28335831"
        )

    def test_cadena_b_resumen(self):
        out = cascada.ejecutar(json.loads(norm(SEED_B)))
        self.assertEqual(
            h(out["resumen"]), "d91d1050722796044f095936e1ef32e913a4bd88b2d00cac7ae2a899e730244b"
        )
