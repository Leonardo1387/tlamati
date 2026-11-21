"""Modulo m17: contrato NO esta aqui; revelado con verify.py --reveal 16."""

import hashlib


def paso(v: dict) -> dict:
    crudo = v["ticket"].encode("utf-8")
    digest = hashlib.sha256(crudo).hexdigest()
    v["firma_ticket"] = digest[:16]
    return v
