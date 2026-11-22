"""M8a — Sidecar de metadatos derivados para memoria (donor: ai-memory M8).

memory/.meta.json: {"version": 1, "entries": {"<key>": {...}}}
- key = sha1_16(texto normalizado de la entrada)  # normalizar: " ".join(e.split())
- valor = {"created_at": iso, "last_touched_at": iso, "touch_count": int}
DERIVADO Y RECONSTRUIBLE: si no existe o se corrompe, se regenera vacío sin
tocar MEMORY.md/USER.md (invariante 1). Nunca se renderiza al prompt
(invariante 4). Escritura atómica igual que store._write (tmp + replace).

M8b añade cold_entries() (tiers HOT/COLD advisory — invariante 3: no se
evicta nada; solo se reporta).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

META_FILENAME = ".meta.json"
VERSION = 1

COLD_DAYS = 45          # > 45 días sin touch = COLD
HOT_TOUCHES = 2         # touch_count >= 2 = HOT por más vieja que sea
HOT_RECENT_DAYS = 14    # tocada hace <= 14 días = HOT


def _empty() -> dict:
    return {"version": VERSION, "entries": {}}


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryMeta:
    """Uso: load() → mutar (touch/forget/reconcile) → save(). Todo fail-soft:
    un sidecar corrupto o ausente se regenera vacío; la memoria manda."""

    def __init__(self, dir_path: Path) -> None:
        self.path = Path(dir_path) / META_FILENAME
        self._data: dict = _empty()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Carga perezosa: mutar sin load() explícito funciona igual."""
        if not self._loaded:
            self.load()

    # ------------------------------------------------------------- key
    @staticmethod
    def key(entry_text: str) -> str:
        norm = " ".join(entry_text.split())
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]

    # ------------------------------------------------------------ load
    def load(self) -> dict:
        """Tolerante total: ausente/corrupto/estructura inválida → vacío.
        Lee de disco UNA vez por instancia; llamadas posteriores devuelven el
        estado vivo en memoria (touch/forget/reconcile sin save intermedio)."""
        if self._loaded:
            return self._data
        self._data = _empty()
        self._loaded = True
        try:
            if self.path.is_file():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and isinstance(raw.get("entries"), dict):
                    entries = {
                        k: v
                        for k, v in raw["entries"].items()
                        if isinstance(k, str) and isinstance(v, dict)
                    }
                    self._data = {"version": VERSION, "entries": entries}
        except (OSError, json.JSONDecodeError):
            self._data = _empty()
        return self._data

    # ----------------------------------------------------------- touch
    def touch(self, entry_text: str, *, when: datetime | None = None) -> None:
        """Crea-o-actualiza: last_touched_at=now, touch_count+=1; si es nuevo,
        created_at=now. Señal de uso en tlamati: replace/remove/dream tocó la
        entrada (add = nacimiento)."""
        self._ensure_loaded()
        now = when or _now()
        iso = now.isoformat()
        k = self.key(entry_text)
        entries = self._data["entries"]
        e = entries.get(k)
        if isinstance(e, dict) and isinstance(e.get("touch_count"), int):
            e["touch_count"] += 1
            e["last_touched_at"] = iso
        else:
            entries[k] = {
                "created_at": iso,
                "last_touched_at": iso,
                "touch_count": 1,
            }

    # ---------------------------------------------------------- forget
    def forget(self, entry_text: str) -> None:
        """Borra la clave (entrada eliminada). Inexistente = no-op."""
        self._ensure_loaded()
        self._data["entries"].pop(self.key(entry_text), None)

    # ------------------------------------------------------- reconcile
    def reconcile(self, live_entries: list[str]) -> None:
        """M8a.2: descarta claves fantasma (entradas borradas a mano que
        dejaron basura en el sidecar). live_entries = entradas actuales de
        MEMORY.md + USER.md."""
        self._ensure_loaded()
        live_keys = {self.key(e) for e in live_entries}
        self._data["entries"] = {
            k: v for k, v in self._data["entries"].items() if k in live_keys
        }

    # ------------------------------------------------------------ save
    def save(self) -> None:
        """Atómico (tmp + replace), igual que store._write."""
        self._ensure_loaded()
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        tmp.replace(self.path)

    # ------------------------------------------------------ M8b: tiers
    def cold_entries(
        self,
        live: dict[str, list[str]],
        now: datetime | None = None,
        cold_days: int = COLD_DAYS,
    ) -> list[tuple[str, str, int]]:
        """live = {"memory": [entradas...], "user": [...]}.
        Devuelve [(target, entrada, días sin touch)] para entradas COLD.
        Reglas M8b (advisory puro, invariante 3 — no se evicta nada):
        - HOT: touch_count >= 2 o edad <= 14 días desde last_touched_at.
        - COLD: edad > cold_days sin touch.
        - Sin registro / fecha corrupta → HOT (beneficio de la duda; el
          sidecar nace vacío en installs existentes).
        now inyectable para tests deterministas."""
        self._ensure_loaded()
        ref = now or _now()
        entries = self._data["entries"]
        cold: list[tuple[str, str, int]] = []
        for target, texts in live.items():
            for text in texts:
                meta = entries.get(self.key(text))
                if not isinstance(meta, dict):
                    continue  # sin registro → hot
                tc = meta.get("touch_count")
                if isinstance(tc, int) and tc >= HOT_TOUCHES:
                    continue  # usada → hot
                last = meta.get("last_touched_at")
                try:
                    last_dt = datetime.fromisoformat(str(last))
                except (TypeError, ValueError):
                    continue  # fecha corrupta → hot
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=UTC)
                age_days = (ref - last_dt) // timedelta(days=1)
                if age_days > cold_days:
                    cold.append((target, text, int(age_days)))
        cold.sort(key=lambda c: -c[2])  # más fría primero
        return cold


def open_meta(dir_path: Path, live_entries: list[str]) -> MemoryMeta:
    """M8a.2: punto de entrada único — carga el sidecar, reconcilia claves
    fantasma contra las entradas vivas y persiste SOLO si hubo cambios.
    Fail-soft: cualquier fallo devuelve un sidecar vacío usable."""
    m = MemoryMeta(dir_path)
    try:
        m.load()
        before = len(m._data["entries"])
        m.reconcile(live_entries)
        if len(m._data["entries"]) != before:
            m.save()
    except Exception:
        m = MemoryMeta(dir_path)
    return m
