import hashlib
import os
import subprocess
import sys
from pathlib import Path

fallos = []

esperados = {
    "tests/test_moneda.py": "3a268c31bdc94f471a2051e2b0a0b2504ef7447cb5324800de4a847a5813d9d3",
    "tests/test_formato.py": "68056a0540cf4cb45266a8700566795517bda2c402660dd07ac7c6c30e99f717",
}
for rel, h in esperados.items():
    p = Path(rel)
    if not p.is_file():
        fallos.append(f"{rel} desapareció")
    elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
        fallos.append(f"{rel} fue modificado (prohibido tocar tests)")

# entorno LIMPIO: sin APP_REGION heredada
env = {k: v for k, v in os.environ.items() if k != "APP_REGION"}
proc = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "tests", "-v"],
    capture_output=True,
    text=True,
    env=env,
    timeout=60,
)
out = proc.stdout + proc.stderr
if proc.returncode != 0:
    fallos.append("la suite no pasa en entorno limpio:\n" + out[-600:])
if "Ran 5 tests" not in out:
    fallos.append("se esperan exactamente 5 tests corridos (ni borrados ni de relleno)")
if "skipped" in out.lower():
    fallos.append("hay tests saltados (prohibido skip)")

if fallos:
    for f in fallos:
        print(f"FALLA: {f}")
    sys.exit(1)
print("VERIFY OK")
