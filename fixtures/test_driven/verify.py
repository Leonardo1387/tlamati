import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
    capture_output=True,
    text=True,
    timeout=60,
)
if proc.returncode != 0:
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-15:]
    for ln in tail:
        print(f"FALLA: {ln}")
    sys.exit(1)
print("VERIFY OK")
