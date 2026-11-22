"""M8a — tests del sidecar de metadatos (donor: ai-memory M8).

Contrato: memory/.meta.json DERIVADO y RECONSTRUIBLE. Nunca toca
MEMORY.md/USER.md; nunca se renderiza al prompt; fallo NUNCA aborta.
"""

import json
from datetime import UTC
from pathlib import Path

from tlamati.memory.meta import MemoryMeta


def test_key_normaliza_whitespace():
    assert MemoryMeta.key("  hola   mundo ") == MemoryMeta.key("hola mundo")
    assert MemoryMeta.key("hola mundo") != MemoryMeta.key("hola  mundos")


def test_key_es_sha1_16_estable():
    k = MemoryMeta.key("entrada de prueba")
    assert len(k) == 16
    assert k == MemoryMeta.key("entrada de prueba")


def test_roundtrip_touch_save_load(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("el usuario prefiere vim")
    m.save()
    m2 = MemoryMeta(tmp_path)
    data = m2.load()
    k = MemoryMeta.key("el usuario prefiere vim")
    assert k in data["entries"]
    e = data["entries"][k]
    assert e["touch_count"] == 1
    assert e["created_at"] == e["last_touched_at"]


def test_touch_repetido_sube_count_y_cambia_last_touched(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("x viva")
    first = m.load()["entries"][MemoryMeta.key("x viva")]["created_at"]
    m.touch("x viva")
    e = m.load()["entries"][MemoryMeta.key("x viva")]
    assert e["touch_count"] == 2
    assert e["created_at"] == first


def test_load_archivo_corrupto_devuelve_vacio(tmp_path: Path):
    (tmp_path / ".meta.json").write_text("{basura", encoding="utf-8")
    m = MemoryMeta(tmp_path)
    data = m.load()
    assert data == {"version": 1, "entries": {}}


def test_load_inexistente_devuelve_vacio(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    assert m.load() == {"version": 1, "entries": {}}


def test_forget_borra_clave(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("morirá")
    m.forget("morirá")
    assert MemoryMeta.key("morirá") not in m.load()["entries"]


def test_forget_inexistente_es_noop(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.forget("nunca existió")  # no raise
    m.save()


def test_entrada_duplicada_mismo_key_no_rompe(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("  dup   licada ")
    m.touch("dup licada")
    assert m.load()["entries"][MemoryMeta.key("dup licada")]["touch_count"] == 2


def test_save_atomico_y_sidecar_en_punto_meta(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("a")
    m.save()
    p = tmp_path / ".meta.json"
    assert p.is_file()
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_reconcile_descarta_fantasmas(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("entrada viva")
    m.touch("entrada fantasma")
    m.save()
    m2 = MemoryMeta(tmp_path)
    m2.reconcile(["entrada viva"])
    m2.save()
    data = MemoryMeta(tmp_path).load()
    assert MemoryMeta.key("entrada viva") in data["entries"]
    assert MemoryMeta.key("entrada fantasma") not in data["entries"]


def test_reconcile_con_entrada_normalizada(tmp_path: Path):
    m = MemoryMeta(tmp_path)
    m.touch("hola mundo")
    m.save()
    m2 = MemoryMeta(tmp_path)
    m2.reconcile(["  hola   mundo "])  # misma entrada, distinto whitespace
    m2.save()
    assert MemoryMeta.key("hola mundo") in MemoryMeta(tmp_path).load()["entries"]


def test_cold_entries_con_now_inyectable(tmp_path: Path):
    """M8b depende de esto: entrada vieja sin touch = cold; reciente = hot."""
    from datetime import datetime, timedelta

    MemoryMeta(tmp_path)
    now = datetime(2026, 11, 21, tzinfo=UTC)
    vieja = (now - timedelta(days=60)).isoformat()
    reciente = (now - timedelta(days=5)).isoformat()
    raw = {
        "version": 1,
        "entries": {
            MemoryMeta.key("fría"): {
                "created_at": vieja,
                "last_touched_at": vieja,
                "touch_count": 1,
            },
            MemoryMeta.key("caliente"): {
                "created_at": reciente,
                "last_touched_at": reciente,
                "touch_count": 1,
            },
        },
    }
    (tmp_path / ".meta.json").write_text(json.dumps(raw), encoding="utf-8")
    m2 = MemoryMeta(tmp_path)
    cold = m2.cold_entries({"memory": ["fría", "caliente", "sin registro"]}, now=now)
    targets = [c[1] for c in cold]
    assert targets == ["fría"]  # sin registro → hot (beneficio de la duda)
    assert cold[0][0] == "memory" and cold[0][2] == 60


def test_cold_entries_touch_count_alto_nunca_cold(tmp_path: Path):
    """touch_count >= 2 = HOT por más vieja que sea (M8b: uso reciente pesa)."""
    import json as _json
    from datetime import datetime, timedelta

    now = datetime(2026, 11, 21, tzinfo=UTC)
    vieja = (now - timedelta(days=100)).isoformat()
    raw = {
        "version": 1,
        "entries": {
            MemoryMeta.key("usada"): {
                "created_at": vieja,
                "last_touched_at": vieja,
                "touch_count": 3,
            }
        },
    }
    (tmp_path / ".meta.json").write_text(_json.dumps(raw), encoding="utf-8")
    m = MemoryMeta(tmp_path)
    assert m.cold_entries({"memory": ["usada"]}, now=now) == []


def test_fecha_corrupta_trata_como_hot(tmp_path: Path):
    from datetime import datetime

    raw = {
        "version": 1,
        "entries": {
            MemoryMeta.key("rota"): {
                "created_at": "no-es-fecha",
                "last_touched_at": "tampoco",
                "touch_count": 1,
            }
        },
    }
    (tmp_path / ".meta.json").write_text(json.dumps(raw), encoding="utf-8")
    m = MemoryMeta(tmp_path)
    assert m.cold_entries({"memory": ["rota"]}, now=datetime.now(UTC)) == []


# ------------------------------------------------------- M8a cableado


def test_apply_batch_actualiza_sidecar(tmp_path: Path):
    """Integración: add→touch, replace→forget+touch, remove→forget."""
    from tlamati.memory.store import MemoryStore

    meta = MemoryMeta(tmp_path)
    store = MemoryStore(tmp_path, meta=meta)
    store.apply_batch("memory", [{"action": "add", "content": "dato uno"}])
    assert MemoryMeta.key("dato uno") in MemoryMeta(tmp_path).load()["entries"]

    store.apply_batch(
        "memory",
        [{"action": "replace", "content": "dato uno v2", "old_text": "dato uno"}],
    )
    m2 = MemoryMeta(tmp_path).load()["entries"]
    assert MemoryMeta.key("dato uno") not in m2
    assert MemoryMeta.key("dato uno v2") in m2

    store.apply_batch("memory", [{"action": "remove", "old_text": "dato uno v2"}])
    assert MemoryMeta.key("dato uno v2") not in MemoryMeta(tmp_path).load()["entries"]


def test_sidecar_roto_no_aborta_batch(tmp_path: Path):
    """Fail-soft: sidecar que revienta al guardar → la memoria SE ESCRIBE igual."""
    from tlamati.memory.store import MemoryStore

    class MetaRoto(MemoryMeta):
        def save(self) -> None:
            raise OSError("disco lleno simulado")

    store = MemoryStore(tmp_path, meta=MetaRoto(tmp_path))
    stats = store.apply_batch("memory", [{"action": "add", "content": "sobreviví"}])
    assert stats.entries == 1
    assert "sobreviví" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")


def test_store_sin_meta_comporta_igual(tmp_path: Path):
    """Default None = conducta anterior byte-idéntica (tests viejos intactos)."""
    from tlamati.memory.store import MemoryStore

    store = MemoryStore(tmp_path)
    store.apply_batch("memory", [{"action": "add", "content": "x"}])
    assert not (tmp_path / ".meta.json").exists()


def test_open_meta_reconcilia_fantasmas(tmp_path: Path):
    from tlamati.memory.meta import open_meta

    m = MemoryMeta(tmp_path)
    m.touch("viva")
    m.touch("fantasma")
    m.save()
    m2 = open_meta(tmp_path, ["viva"])
    data = m2.load()
    assert MemoryMeta.key("viva") in data["entries"]
    assert MemoryMeta.key("fantasma") not in data["entries"]
