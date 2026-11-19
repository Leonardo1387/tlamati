"""E3e PASO C — tests de normalización de rutas Windows → /mnt/<letra>.

MOUNT_ROOT se monkeypachea a un árbol tmp para no depender del /mnt real
(portable a CI Linux sin WSL). Tests de sandbox con bwrap: skip si no está.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tlamati.tools import winpath
from tlamati.tools.files import make_file_tools
from tlamati.tools.winpath import WinPathError, normalize_win_in_command, normalize_win_path


@pytest.fixture()
def fake_mnt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Árbol /mnt falso con drives c y d montados."""
    root = tmp_path / "mnt"
    (root / "c" / "Users" / "Admin" / "Desktop").mkdir(parents=True)
    (root / "d" / "dir").mkdir(parents=True)
    (root / "c" / "Users" / "Admin" / "Desktop" / "notas.txt").write_text(
        "hola windows", encoding="utf-8"
    )
    monkeypatch.setattr(winpath, "MOUNT_ROOT", root)
    return root


# ---------------------------------------------------------------- unit
class TestNormalizeWinPath:
    def test_backslashes(self, fake_mnt: Path) -> None:
        assert normalize_win_path("C:\\Users\\Admin\\Desktop\\notas.txt") == str(
            fake_mnt / "c/Users/Admin/Desktop/notas.txt"
        )

    def test_forward_slashes(self, fake_mnt: Path) -> None:
        assert normalize_win_path("D:/dir/archivo.md") == str(fake_mnt / "d/dir/archivo.md")

    def test_lowercase_drive(self, fake_mnt: Path) -> None:
        assert normalize_win_path("c:\\Users") == str(fake_mnt / "c/Users")

    def test_duplicate_slashes_collapsed(self, fake_mnt: Path) -> None:
        assert normalize_win_path("C:\\\\Users\\\\Admin") == str(fake_mnt / "c/Users/Admin")

    def test_bare_drive_root(self, fake_mnt: Path) -> None:
        assert normalize_win_path("C:") == str(fake_mnt / "c")
        assert normalize_win_path("C:\\") == str(fake_mnt / "c")
        assert normalize_win_path("C:/") == str(fake_mnt / "c")

    def test_idempotent_mnt(self, fake_mnt: Path) -> None:
        intact = "/mnt/c/Users/Admin/Desktop"
        assert normalize_win_path(intact) == intact

    def test_relative_intact(self, fake_mnt: Path) -> None:
        for s in ("src/main.py", "./x.txt", "notas.md", "..", "."):
            assert normalize_win_path(s) == s

    def test_home_intact(self, fake_mnt: Path) -> None:
        assert normalize_win_path("~/code/x.py") == "~/code/x.py"

    def test_absolute_unix_intact(self, fake_mnt: Path) -> None:
        assert normalize_win_path("/home/u/archivo") == "/home/u/archivo"

    def test_drive_not_mounted_honest_error(self, fake_mnt: Path) -> None:
        with pytest.raises(WinPathError) as exc:
            normalize_win_path("Z:\\cosas\\x.txt")
        msg = str(exc.value)
        assert "Windows" in msg
        assert "Z:" in msg
        # mensaje honesto: nunca un path inventado
        assert "mnt" in msg

    def test_not_a_drive_letter_colon(self, fake_mnt: Path) -> None:
        # "nota: algo" no es ruta Windows (falta separador tras los dos puntos)
        assert normalize_win_path("nota: algo") == "nota: algo"

    def test_time_like_token_untouched(self, fake_mnt: Path) -> None:
        # un token como "12:30" no empieza con letra → intacto
        assert normalize_win_path("12:30") == "12:30"


class TestNormalizeWinInCommand:
    def test_translates_embedded_paths(self, fake_mnt: Path) -> None:
        cmd = "cat C:\\Users\\Admin\\Desktop\\notas.txt | head -5"
        out = normalize_win_in_command(cmd)
        assert f"cat {fake_mnt}/c/Users/Admin/Desktop/notas.txt | head -5" == out

    def test_quoted_path(self, fake_mnt: Path) -> None:
        cmd = "ls 'C:\\Users\\Admin'"
        out = normalize_win_in_command(cmd)
        assert out == f"ls '{fake_mnt}/c/Users/Admin'"

    def test_unmounted_drive_left_intact(self, fake_mnt: Path) -> None:
        cmd = "cat Z:\\x.txt"
        assert normalize_win_in_command(cmd) == cmd

    def test_no_windows_paths_noop(self, fake_mnt: Path) -> None:
        cmd = "git status && ls /mnt/c/Users"
        assert normalize_win_in_command(cmd) == cmd

    def test_url_untouched(self, fake_mnt: Path) -> None:
        # "https://x" no debe confundirse (la frontera izquierda bloquea)
        cmd = "curl https://example.com/c:/cosa"
        assert normalize_win_in_command(cmd) == cmd


# ---------------------------------------------------------------- integración
def _tool(tools: list[Any], name: str) -> Any:
    return next(t for t in tools if t.name == name)


class TestReadFileIntegration:
    async def test_read_windows_path(self, fake_mnt: Path, tmp_path: Path) -> None:
        tools = make_file_tools(tmp_path)
        result = await _tool(tools, "read_file").run(
            {"path": "C:\\Users\\Admin\\Desktop\\notas.txt"}
        )
        assert "hola windows" in result
        assert not result.startswith("ERROR")

    async def test_read_unmounted_drive_honest(self, fake_mnt: Path, tmp_path: Path) -> None:
        tools = make_file_tools(tmp_path)
        result = await _tool(tools, "read_file").run({"path": "Z:\\cosas\\x.txt"})
        assert result.startswith("ERROR")
        assert "Windows" in result

    async def test_write_and_edit_windows_path(self, fake_mnt: Path, tmp_path: Path) -> None:
        tools = make_file_tools(tmp_path)
        target = "D:\\dir\\nuevo.txt"
        r = await _tool(tools, "write_file").run({"path": target, "content": "v1"})
        assert r.startswith("wrote")
        assert (fake_mnt / "d/dir/nuevo.txt").read_text(encoding="utf-8") == "v1"
        r2 = await _tool(tools, "edit").run(
            {"path": target, "old_string": "v1", "new_string": "v2"}
        )
        assert "edited" in r2
        assert (fake_mnt / "d/dir/nuevo.txt").read_text(encoding="utf-8") == "v2"


class TestSearchIntegration:
    async def test_search_windows_dir(self, fake_mnt: Path, tmp_path: Path) -> None:
        pytest.importorskip("shutil")
        import shutil

        if shutil.which("rg") is None:
            pytest.skip("ripgrep no instalado")
        from tlamati.tools.search import make_search_tools

        tools = make_search_tools(tmp_path)
        result = await _tool(tools, "search_files").run(
            {"pattern": "hola windows", "path": "C:\\Users\\Admin\\Desktop"}
        )
        assert "notas.txt" in result

    async def test_search_unmounted_honest(self, fake_mnt: Path, tmp_path: Path) -> None:
        from tlamati.tools.search import make_search_tools

        tools = make_search_tools(tmp_path)
        result = await _tool(tools, "search_files").run({"pattern": "x", "path": "Z:\\no\\existe"})
        assert result.startswith("ERROR")
        assert "Windows" in result


# ---------------------------------------------------------------- sandbox real
@pytest.mark.skipif(not Path("/mnt/c").is_dir(), reason="sin /mnt/c (no es WSL) — sandbox test N/A")
class TestSandboxSeesMntC:
    def test_bwrap_exposes_mnt_c(self) -> None:
        """OJO SANDBOX del handoff E3e §1b: ¿/mnt/c es visible DENTRO de la
        jaula? El perfil bindea / completo read-only, así que /mnt/c debe
        entrar. Prueba REAL con bwrap, no asumida."""
        import shutil
        import subprocess

        if shutil.which("bwrap") is None:
            pytest.skip("bwrap no instalado")
        from tlamati.sandbox.bwrap import SandboxProfile, wrap_command

        # archivo semilla real en /tmp (ro-bind / incluye /tmp)
        wrapped = wrap_command(
            "ls /mnt/c >/dev/null && echo MNT_C_VISIBLE",
            SandboxProfile(workdir=Path("/tmp")),
        )
        assert wrapped is not None
        proc = subprocess.run(wrapped, shell=True, capture_output=True, text=True, timeout=30)
        assert "MNT_C_VISIBLE" in proc.stdout
        assert proc.returncode == 0
