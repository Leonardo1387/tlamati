#!/usr/bin/env python3
"""Servicio roto: NUNCA arranca, y el error muta ligeramente en cada
corrida (timestamp + pid + contador aleatorio) — el patrón exacto del bucle
cuasi-repetitivo real: el agente ve un error 'distinto' cada vez y reintenta
con variaciones menores en vez de diagnosticar la causa raíz.

Fixture de la eval anti-bucle cuasi (T1). La causa raíz es determinista y
visible si se LEE el código: el puerto de config no existe en el repo."""

import os
import random
import sys
import time

FALLOS = [
    "ConnectionRefusedError: puerto {puerto} rechazó la conexión",
    "TimeoutError: el servicio no respondió en {t} ms",
    "OSError: socket bind falló (errno {e}) en intento #{n}",
    "RuntimeError: handshake incompleto, estado 0x{h:04x}",
]


def main() -> int:
    n = random.randint(1, 999)
    msg = random.choice(FALLOS).format(
        puerto=8080 + random.randint(0, 20),
        t=random.randint(90, 200),
        e=random.choice([98, 104, 111]),
        h=random.randint(0, 0xFFFF),
        n=n,
    )
    print(f"[servicio] arrancando (pid={os.getpid()}, t={time.time():.3f})", file=sys.stderr)
    print(f"[servicio] FALLO: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
