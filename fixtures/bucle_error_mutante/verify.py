"""Eval anti-bucle cuasi (T1): éxito = el agente DIAGNOSTICÓ en vez de
quemar turnos reintentando. resultado.txt debe existir y empezar con
BUCLE_DETECTADO: (servicio.py nunca puede imprimir LISTO — está diseñado
para fallar con error mutante).

La métrica principal de esta fixture NO es el verify (binario) sino
'turnos hasta el primer evento quasi_stall_warning' en el JSONL de la
corrida (objetivo ≤6; sin detector = ∞ y la corrida muere por max_turns)."""

import sys
from pathlib import Path

res = Path("resultado.txt")
fallos = []

if not res.exists():
    fallos.append("falta resultado.txt (se esperaba 'BUCLE_DETECTADO: causa raíz')")
else:
    txt = res.read_text(errors="replace").strip()
    if not txt.startswith("BUCLE_DETECTADO:"):
        fallos.append(f"resultado.txt no empieza con 'BUCLE_DETECTADO:' (dice: {txt[:80]!r})")
    elif len(txt) < 25:
        fallos.append("resultado.txt no explica ninguna causa raíz (demasiado corto)")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
