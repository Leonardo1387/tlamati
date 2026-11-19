"""E3e PASO C — normalización de rutas Windows a puntos de montaje WSL.

Problema real (autopsia dogfooding sesión 20, seq 21-22): el fundador pegó
``C:\\Users\\Admin\\Desktop\\...`` tal cual y read_file falló con "no such
file: /home/usuario/C:\\Users\\..." — Path() trató la ruta Windows como
relativa. El fundador espera que tlamati "tenga ojos sobre mis archivos en
la computadora" (Hermes WSL resuelve esto de facto vía /mnt/<letra>).

Contrato:

- Input que empieza con letra + ":" + separador (``C:\\``, ``D:/``, ``c:\\``)
  → traducir a ``/mnt/<letra-minúscula>/`` con backslashes→slashes y slashes
  duplicados colapsados.
- IDEMPOTENTE: ``/mnt/c/...`` sale intacto; rutas relativas intactas;
  ``~`` intacto (no toca expanduser, que ya hace _resolve).
- Fallo HONESTO: si el punto de montaje ``/mnt/<letra>`` no existe (no es
  WSL, o la letra no está montada) → WinPathError con mensaje que dice la
  verdad; NUNCA se inventa un path.

Fuera de scope (decisión handoff E3d §5b): detección de "Desktop" genérico;
rutas UNC (``\\\\server\\share``). La normalización letra: resuelve el caso real.
"""

from __future__ import annotations

import re
from pathlib import Path

# Punto de montaje raíz de los drives Windows en WSL. Variable de módulo
# (no constante privada) para que los tests puedan monkeypatchearla a un
# árbol temporal sin tocar /mnt real.
MOUNT_ROOT = Path("/mnt")

# letra + ":" + (separador + resto | fin).  "C:" a secas → raíz del drive.
_DRIVE_RE = re.compile(r"^([A-Za-z]):(?:[\\/](.*))?$")


class WinPathError(ValueError):
    """El input PARECE ruta Windows pero no se puede traducir honestamente."""


def normalize_win_path(path_str: str) -> str:
    """Traduce una ruta Windows a su equivalente WSL; idempotente.

    Devuelve el string normalizado (listo para Path()). Lanza WinPathError
    si parece ruta Windows pero el drive no está montado — el caller lo
    convierte en un ERROR de tool honesto para el modelo.
    """
    m = _DRIVE_RE.match(path_str)
    if m is None:
        return path_str  # no parece ruta Windows → intacto (relativa, ~, /mnt/...)
    drive = m.group(1).lower()
    rest = m.group(2) or ""
    rest = rest.replace("\\", "/")
    while "//" in rest:
        rest = rest.replace("//", "/")
    rest = rest.strip("/")
    mount = MOUNT_ROOT / drive
    if not mount.is_dir():
        raise WinPathError(
            f"la ruta parece de Windows ({path_str}) pero el drive {drive.upper()}: "
            f"no está montado en {mount} — este sistema no es WSL o el drive no existe"
        )
    if rest:
        return f"{mount}/{rest}"
    return str(mount)


# Token de ruta Windows dentro de un comando shell: letra ":" separador,
# precedida de frontera (no parte de otra palabra/path) y seguida de chars
# de ruta (se corta en whitespace, comillas y operadores shell).
_CMD_TOKEN_RE = re.compile(
    r"""(?<![A-Za-z0-9_/.~-])           # frontera izquierda (no pegar con / ni .)
        (?P<full>[A-Za-z]:[\\/][^\s'"|;&<>()]*)""",
    re.VERBOSE,
)


def normalize_win_in_command(cmd: str) -> str:
    """Traduce rutas Windows sueltas dentro de un comando shell (tool terminal).

    Best-effort y fail-soft: cada token que no se puede traducir (drive no
    montado) se deja INTACTO — el comando fallará por sí mismo con su propio
    error honesto. No lanza excepciones.
    """

    def _sub(m: re.Match[str]) -> str:
        token = m.group("full")
        try:
            return normalize_win_path(token)
        except WinPathError:
            return token

    return _CMD_TOKEN_RE.sub(_sub, cmd)
