"""B3 — jaula bwrap para el tool terminal.

Perfil default (GUIA §B3):

    bwrap --ro-bind / / --bind <workdir> <workdir> --dev /dev --proc /proc
          --chdir <workdir> --die-with-parent --unshare-all [--share-net]

filesystem read-only + workdir escribible + SIN red (--unshare-all incluye
--unshare-net). La red es un permiso SEPARADO (``net=True`` → --share-net);
B4 (policy/) lo gobernará por configuración de permisos.

Decisiones documentadas (HANDOFF_FASE_B3 pedía decidir en B3):

1. EVALS: el sandbox se activa también en evals. El workspace del eval ES el
   workdir que se bindea rw, así que los fixtures que viven en tmp_path
   funcionan igual. /tmp queda read-only DENTRO de la jaula; verify.py corre
   FUERA del sandbox (subprocess directo del runner), sin conflicto.
2. DEGRADACIÓN HONESTA: si bwrap no existe, ``wrap_command`` devuelve None y
   el terminal corre sin jaula — pero el CLI lo avisa explícitamente al
   arrancar y el resultado del tool lleva una nota. Nunca silencio: el
   usuario debe saber que NO está protegido.
3. ENTORNO: se hereda el env del padre (PATH/HOME necesarios para que los
   comandos funcionen). Las API keys del provider quedan visibles al comando
   enjaulado; aceptable en un harness local mono-usuario, se documenta aquí
   y B4 podrá endurecer (--clearenv + whitelist).
4. Sin --unshare-user explícito: --unshare-all ya cubre user namespace;
   verificado en WSL (bwrap 0.9.0, ``--unshare-all echo ok`` → "ok").
"""

from __future__ import annotations

import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxProfile:
    """Qué jaula aplicar: workdir escribible, red opcional (default OFF)."""

    workdir: Path
    net: bool = False


def bwrap_available() -> bool:
    """True si el binario bwrap está en el PATH."""
    return shutil.which("bwrap") is not None


def build_bwrap_argv(profile: SandboxProfile) -> list[str]:
    """Argv completo de bwrap (sin el comando a ejecutar)."""
    wd = str(profile.workdir)
    argv = [
        "bwrap",
        "--ro-bind",
        "/",
        "/",
        "--bind",
        wd,
        wd,
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--chdir",
        wd,
        "--die-with-parent",
        "--unshare-all",
    ]
    if profile.net:
        argv.append("--share-net")
    return argv


def wrap_command(cmd: str, profile: SandboxProfile) -> str | None:
    """Envuelve ``cmd`` en la jaula. None si bwrap no existe (degradación).

    El resultado es una línea shell-ready (todo citado con shlex) porque el
    tool terminal usa create_subprocess_shell.
    """
    if not bwrap_available():
        return None
    argv = build_bwrap_argv(profile)
    quoted = " ".join(shlex.quote(a) for a in argv)
    return f"{quoted} -- /bin/sh -c {shlex.quote(cmd)}"
