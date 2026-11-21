"""Modulo s27 del ducto: aplica SU regla del contrato (descripciones en docs/REGLAS.md)."""

import hashlib
import json


def paso(v: dict) -> dict:
    doc = {"suma": v["suma"], "checksum": v["checksum"]}
    v["firma"] = hashlib.sha256(json.dumps(doc).encode()).hexdigest()[:16]
    return v
