"""Sesión 25 (dogfooding #3): bloque ambiental + list_dir.

El bug real: el modelo negó tener acceso al filesystem CON tools registradas.
Fix: (a) list_dir para VER dirs; (b) environment_block en el system prompt —
multi-plataforma (Windows/mac/Linux/WSL), cero rutas inventadas, byte-estable
por corrida (cache sagrada).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tlamati.env_info import environment_block, is_wsl, user_dirs
from tlamati.tools import files as files_mod


# ------------------------------------------------------------------ env_info
def test_environment_block_contiene_lo_esencial(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    block = environment_block(tmp_path, home=home, wsl=False)
    assert "ENTORNO" in block
    assert str(tmp_path) in block  # cwd
    assert str(home / "Desktop") in block  # desktop REAL, verificado en disco
    assert "ACCESO COMPLETO" in block
    assert "NUNCA digas que no puedes" in block


def test_environment_block_no_inventa_dirs_inexistentes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    block = environment_block(tmp_path, home=home, wsl=False)
    assert "Desktop" not in block  # no existe → no se declara
    assert "Downloads" not in block


def test_user_dirs_wsl_encuentra_desktop_en_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WSL: el escritorio real vive en /mnt/<letra>/Users/<user>/Desktop."""
    fake_mnt = tmp_path / "mnt"
    win_desktop = fake_mnt / "c" / "Users" / "jane" / "Desktop"
    win_desktop.mkdir(parents=True)
    import tlamati.tools.winpath as winpath_mod

    monkeypatch.setattr(winpath_mod, "MOUNT_ROOT", fake_mnt)
    home = tmp_path / "home"
    home.mkdir()
    dirs = user_dirs(home, wsl=True)
    assert win_desktop in dirs["desktop"]


def test_user_dirs_wsl_excluye_perfiles_sistema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All Users/Default/Default User/Public NO son usuarios reales."""
    fake_mnt = tmp_path / "mnt"
    for user in ("jane", "All Users", "Default", "Default User", "Public"):
        (fake_mnt / "c" / "Users" / user / "Desktop").mkdir(parents=True)
    import tlamati.tools.winpath as winpath_mod

    monkeypatch.setattr(winpath_mod, "MOUNT_ROOT", fake_mnt)
    home = tmp_path / "home"
    home.mkdir()
    dirs = user_dirs(home, wsl=True)
    assert dirs["desktop"] == [fake_mnt / "c" / "Users" / "jane" / "Desktop"]


def test_user_dirs_linux_nativo_sin_wsl(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "Documentos").mkdir(parents=True)  # nombre español (Linux ES)
    dirs = user_dirs(home, wsl=False)
    assert home / "Documentos" in dirs["documents"]
    assert dirs["desktop"] == []


def test_environment_block_estable_entre_llamadas(tmp_path: Path) -> None:
    """Cache sagrada: mismo workdir/home → bloque byte-idéntico (sin reloj)."""
    home = tmp_path / "home"
    home.mkdir()
    a = environment_block(tmp_path, home=home, wsl=False)
    b = environment_block(tmp_path, home=home, wsl=False)
    assert a == b


# ------------------------------------------------- SEC.3: el agente SABE su red
# Lección dogfood #4 (nemotron): capacidad SIN orden = el modelo dice "no
# puedo" aunque pueda. El bloque ambiental debe declarar el estado de red
# del terminal, y ser byte-estable por corrida (cache sagrada, commit 7751663).


def test_block_declara_red_on(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    block = environment_block(tmp_path, home=home, wsl=False, net=True)
    assert "SÍ tiene acceso a red" in block
    assert "NO tiene acceso a red" not in block


def test_block_declara_red_off_con_alternativa(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    block = environment_block(tmp_path, home=home, wsl=False, net=False)
    assert "NO tiene acceso a red" in block
    # lección dogfood #4: honesto + alternativa, no un "no puedo" seco
    assert "alternativa" in block.lower()
    assert "exit 6" in block  # señal concreta del fallo (terminal.py ya la usa)


def test_block_sin_net_no_declara_nada(tmp_path: Path) -> None:
    """net=None (default) → backward-compat: ni afirma ni niega."""
    home = tmp_path / "home"
    home.mkdir()
    block = environment_block(tmp_path, home=home, wsl=False)
    assert "acceso a red" not in block


def test_block_red_byte_estable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    a = environment_block(tmp_path, home=home, wsl=False, net=True)
    b = environment_block(tmp_path, home=home, wsl=False, net=True)
    assert a == b
    assert a != environment_block(tmp_path, home=home, wsl=False, net=False)


def test_is_wsl_no_crash() -> None:
    assert isinstance(is_wsl(), bool)


# ------------------------------------------------------------------ list_dir
def _tools(workdir: Path) -> dict[str, object]:
    return {t.name: t for t in files_mod.make_file_tools(workdir)}


async def test_list_dir_registrada_y_lista(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "nota.txt").write_text("x")
    tools = _tools(tmp_path)
    assert "list_dir" in tools
    out = await tools["list_dir"].run({"path": str(tmp_path)})  # type: ignore[union-attr]
    assert "[dir]  sub/" in out
    assert "nota.txt" in out
    # dirs primero
    assert out.index("sub/") < out.index("nota.txt")


async def test_list_dir_default_workdir_y_pattern(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("1")
    (tmp_path / "b.txt").write_text("2")
    tools = _tools(tmp_path)
    out = await tools["list_dir"].run({"pattern": "*.md"})  # type: ignore[union-attr]
    assert "a.md" in out
    assert "b.txt" not in out


async def test_list_dir_ruta_inexistente_falla_honesto(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    out = await tools["list_dir"].run({"path": str(tmp_path / "nada")})  # type: ignore[union-attr]
    assert out.startswith("ERROR: not a directory")


async def test_list_dir_acepta_ruta_windows_en_wsl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C:\\Users\\... → /mnt/c/Users/... vía winpath (mock del mount)."""
    import tlamati.tools.winpath as winpath_mod

    fake_mnt = tmp_path / "mnt"
    target = fake_mnt / "c" / "Users" / "jane" / "Desktop"
    target.mkdir(parents=True)
    (target / "meeting.txt").write_text("hola")
    monkeypatch.setattr(winpath_mod, "MOUNT_ROOT", fake_mnt)
    tools = _tools(tmp_path)
    out = await tools["list_dir"].run({"path": "C:\\Users\\jane\\Desktop"})  # type: ignore[union-attr]
    assert "meeting.txt" in out


async def test_list_dir_limit(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x")
    tools = _tools(tmp_path)
    out = await tools["list_dir"].run({"path": str(tmp_path), "limit": 2})  # type: ignore[union-attr]
    assert "[capped at 2]" in out
    assert "5 entries" in out
