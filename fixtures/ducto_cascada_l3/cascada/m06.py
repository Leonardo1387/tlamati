"""Modulo m06: contrato NO esta aqui; revelado con verify.py --reveal 5."""


def paso(v: dict) -> dict:
    trozos = v["slug"].split("-")
    out = []
    for t in trozos:
        out.append(t[::-1])
    v["slug_inverso"] = "-".join(out)
    return v
