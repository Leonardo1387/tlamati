import hashlib
import subprocess
import sys
from pathlib import Path

fallos = []

H_ESPERADO = "b5d67ee454315b6e2c46534ac9805f35fb6c49a73c7f51e2da50ff9acc64b5f4"
p = Path("tests/test_validadores.py")
if not p.is_file():
    fallos.append("tests/test_validadores.py desapareció")
elif hashlib.sha256(p.read_bytes()).hexdigest() != H_ESPERADO:
    fallos.append("los tests fueron modificados (prohibido)")

proc = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "tests", "-v"],
    capture_output=True,
    text=True,
    timeout=60,
)
out = proc.stdout + proc.stderr
if proc.returncode != 0:
    fallos.append("la suite no pasa completa (regresión):\n" + out[-600:])
if "Ran 6 tests" not in out:
    fallos.append("se esperan exactamente 6 tests corridos")
if "skipped" in out.lower():
    fallos.append("hay tests saltados (prohibido skip)")

src = Path("validadores.py").read_text()
for fn in (
    "validar_email",
    "validar_telefono",
    "validar_cp",
    "validar_rfc",
    "validar_curp",
    "validar_fecha",
):
    if f"def {fn}" not in src:
        fallos.append(f"validadores.py perdió la función {fn}")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
