"""M8c — lint cero-LLM de near-duplicates (donor: ai-memory A5, Jaccard).

ADVISORY: nunca muta archivos (invariante 3); exit 0 siempre.
"""

from pathlib import Path

from tlamati.memory.lint import Finding, lint


def test_casi_iguales_dan_finding():
    entries = {
        "memory": [
            "El deploy corre en Railway con plan free",
            "el deploy corre en railway con plan free",  # misma, otro case
        ]
    }
    findings = lint(entries)
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "near_duplicate"
    assert f.score > 0.9


def test_distintas_no_dan_finding():
    entries = {
        "memory": [
            "El deploy corre en Railway",
            "La base de datos usa SQLite con WAL",
        ]
    }
    assert lint(entries) == []


def test_umbral_por_debajo_no_dan_finding():
    entries = {"memory": ["aaa bbb ccc ddd", "ccc ddd eee fff"]}
    # Jaccard = 2/6 ≈ 0.33 < 0.55 default
    assert lint(entries) == []


def test_umbral_explicito():
    entries = {"memory": ["aaa bbb ccc ddd", "ccc ddd eee fff"]}
    findings = lint(entries, threshold=0.3)
    assert len(findings) == 1
    assert 0.3 <= findings[0].score < 0.55


def test_entrada_consigo_misma_no_se_compara():
    entries = {"memory": ["misma entrada única"]}
    assert lint(entries) == []


def test_cross_target_memory_vs_user():
    entries = {
        "memory": ["El usuario prefiere respuestas inline en el chat"],
        "user": ["el usuario prefiere respuestas inline en el chat"],
    }
    findings = lint(entries)
    assert len(findings) == 1
    assert {findings[0].target_a, findings[0].target_b} == {"memory", "user"}


def test_puntuacion_no_rompe_similitud():
    entries = {
        "memory": [
            "Deploy: corre en Railway (plan free).",
            "deploy corre en railway plan free",
        ]
    }
    findings = lint(entries)
    assert len(findings) == 1
    assert findings[0].score > 0.9


def test_orden_determinista():
    entries = {
        "memory": [
            "a b c d e f g",
            "a b c d e f h",
            "a b c d e f i",
        ]
    }
    f1 = lint(entries, threshold=0.5)
    f2 = lint(entries, threshold=0.5)
    assert [(f.entry_a, f.entry_b, f.score) for f in f1] == [
        (f.entry_a, f.entry_b, f.score) for f in f2
    ]
    # ordenado por score descendente
    scores = [f.score for f in f1]
    assert scores == sorted(scores, reverse=True)


def test_vacio_no_rompe():
    assert lint({}) == []
    assert lint({"memory": [], "user": []}) == []


def test_finding_es_frozen():
    f = Finding(
        kind="near_duplicate",
        target_a="memory",
        entry_a="x",
        target_b="user",
        entry_b="x",
        score=1.0,
    )
    try:
        f.score = 0.5  # type: ignore[misc]
        raise AssertionError("debió ser frozen")
    except AttributeError:
        pass


# ------------------------------------------------- M8c CLI memory lint


def test_memory_lint_cli_limpio(capsys, tmp_path: Path):
    from tlamati.cli import main
    from tlamati.memory.store import MemoryStore

    store = MemoryStore(tmp_path)
    store.apply_batch("memory", [{"action": "add", "content": "dato único A"}])
    rc = main(["memory", "lint", "--memory-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "limpia" in out


def test_memory_lint_cli_reporta_duplicados(capsys, tmp_path: Path):
    from tlamati.cli import main
    from tlamati.memory.store import MemoryStore

    store = MemoryStore(tmp_path)
    store.apply_batch(
        "memory",
        [
            {"action": "add", "content": "El deploy corre en Railway plan free"},
            {"action": "add", "content": "el deploy corre en railway plan free!"},
        ],
    )
    rc = main(["memory", "lint", "--memory-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0  # advisory: exit 0 SIEMPRE
    assert "duplicado" in out
    assert "similitud" in out
    assert "Sugerencia" in out
    # NUNCA muta: las dos entradas siguen vivas
    assert len(store.load("memory").entries) == 2
