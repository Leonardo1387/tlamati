"""Modulo m29: contrato NO esta aqui; revelado con verify.py --reveal 28."""


def paso(v: dict) -> dict:
    xs = v["cantidades"]
    filas = []
    i = 0
    while i < len(xs):
        fila = list(xs[i : i + 3])
        filas.append(fila)
        i += 3
    v["matriz"] = filas
    return v
