"""Modulo m08. v['slug'] = titulo minusculas, SIN acentos, no-alfanumericos -> '-',
colapsados y sin '-' en bordes.
"""

import re
import unicodedata


def paso(v: dict) -> dict:
    txt = unicodedata.normalize("NFKD", v["norm"]["titulo"]).lower()
    v["slug"] = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", txt)).strip("-")
    return v
