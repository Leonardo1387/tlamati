"""G2 — gap-analysis del consolidador (donor: gbrain think).

El dream ya lee la transcripción completa; pedirle que además reporte huecos
cuesta 0 llamadas extra. Advisory puro: los gaps NO se escriben a archivo.
"""

from tlamati.memory.dream import DreamReport, parse_dream_output


def test_parse_extrae_gaps_junto_a_operations():
    raw = (
        '{"operations": [], "gaps": ["El usuario mencionó Railway pero no hay '
        'nada guardado", "Posible contradicción: entrada X dice A, la sesión '
        'dijo B"]}'
    )
    ops, gaps = parse_dream_output(raw)
    assert ops == []
    assert len(gaps) == 2
    assert "Railway" in gaps[0]


def test_parse_tolerante_sin_gaps():
    ops, gaps = parse_dream_output('{"operations": []}')
    assert ops == [] and gaps == []


def test_parse_caps_gaps_en_tres_y_300_chars():
    raw = '{"operations": [], "gaps": ["a", "b", "c", "d", "e"]}'
    _, gaps = parse_dream_output(raw)
    assert len(gaps) == 3
    largo = '{"operations": [], "gaps": ["' + "x" * 400 + '"]}'
    _, gaps2 = parse_dream_output(largo)
    assert len(gaps2[0]) <= 300


def test_parse_ignora_gaps_que_no_son_strings():
    raw = '{"operations": [], "gaps": [42, null, {"a": 1}, "sí es string"]}'
    _, gaps = parse_dream_output(raw)
    assert gaps == ["sí es string"]


def test_report_humano_incluye_gaps():
    r = DreamReport(applied=1, gaps=("no hay clave OPENAI en memoria",))
    assert "hueco" in r.human().lower() or "gap" in r.human().lower()


def test_report_sin_gaps_no_cambia():
    r = DreamReport(applied=2)
    assert "hueco" not in r.human().lower()
