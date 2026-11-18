import os
import subprocess
import sys
from pathlib import Path

if not os.path.isdir(".git"):
    print("FALLA: no hay repo git aquí (¿corriste bash setup.sh?)")
    sys.exit(1)
p = Path("culpable.txt")
if not p.exists():
    print("FALLA: falta culpable.txt")
    sys.exit(1)
dado = p.read_text().strip()

log = subprocess.run(["git", "log", "--format=%H %s"], capture_output=True, text=True)
commits = {}
for ln in log.stdout.strip().splitlines():
    h, _, s = ln.partition(" ")
    commits[h] = s
if dado not in commits:
    print(f"FALLA: {dado!r} no es un commit de este repo")
    sys.exit(1)
if not commits[dado].startswith("refactor"):
    print(f"FALLA: {dado[:8]} ({commits[dado]}) no es el commit que rompió formatear_ruta")
    sys.exit(1)
print("VERIFY OK")
