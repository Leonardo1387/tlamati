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
3. ENTORNO (endurecido 25-nov, era el punto 3 abierto de B3): la jaula arranca
   con ``--clearenv`` y SOLO recibe una whitelist de variables inocuas
   (PATH/HOME/LANG/TERM/...) vía ``--setenv``. Las API keys del provider ya NO
   son visibles al comando enjaulado. Fail-closed: toda variable fuera de la
   whitelist se queda fuera. El harness llama al modelo FUERA de la jaula, así
   que los comandos enjaulados (builds/tests) no necesitan credenciales.
4. Sin --unshare-user explícito: --unshare-all ya cubre user namespace;
   verificado en WSL (bwrap 0.9.0, ``--unshare-all echo ok`` → "ok").
"""

from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

# Whitelist de variables de entorno que SÍ entran a la jaula.
# Fail-closed: todo lo demás (API keys, tokens, secrets) se queda fuera.
# El harness llama al modelo FUERA de la jaula — los comandos enjaulados
# (builds, tests, scripts) no necesitan credenciales para funcionar.
_ENV_WHITELIST = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "TERM",
        "SHELL",
        "TMPDIR",
        "EDITOR",
        "PAGER",
        "COLORTERM",
        "NO_COLOR",
        "FORCE_COLOR",
        "PYTHONUTF8",
        "PYTHONDONTWRITEBYTECODE",
    }
)


@dataclass(frozen=True)
class SandboxProfile:
    """Qué jaula aplicar: workdir escribible, red opcional (default OFF)."""

    workdir: Path
    net: bool = False


def bwrap_available() -> bool:
    """True si el binario bwrap está en el PATH."""
    return shutil.which("bwrap") is not None


def build_bwrap_argv(
    profile: SandboxProfile, environ: os._Environ[str] | dict[str, str] | None = None
) -> list[str]:
    """Argv completo de bwrap (sin el comando a ejecutar).

    ``--clearenv`` + whitelist: solo las variables inocuas de _ENV_WHITELIST
    entran a la jaula (vía --setenv). Las API keys del env del padre NO.
    """
    env = os.environ if environ is None else environ
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
        "--clearenv",
    ]
    for name in sorted(_ENV_WHITELIST):
        value = env.get(name)
        if value is not None:
            argv += ["--setenv", name, value]
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
