import sys
from pathlib import Path

p = Path("respuesta.txt")
if not p.exists():
    print("FALLA: falta respuesta.txt")
    sys.exit(1)
dado = p.read_text().strip()
if dado != "ERR-4711":
    print(f"FALLA: respuesta.txt dice {dado!r}, esperado el código FATAL único")
    sys.exit(1)
print("VERIFY OK")
