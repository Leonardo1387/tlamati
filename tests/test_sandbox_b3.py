"""B3 — sandbox bwrap: perfil, wrapper, fuga, red y degradación honesta.

Los tests marcados require_bwrap corren la jaula REAL (bwrap instalado en
esta máquina; si falta, skip honesto — nunca verde falso).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tlamati.sandbox import bwrap as sb
from tlamati.sandbox.bwrap import SandboxProfile, build_bwrap_argv, wrap_command
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry

require_bwrap = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap no instalado")


class TestProfileArgv:
    def test_default_profile_shape(self, tmp_path: Path) -> None:
        argv = build_bwrap_argv(SandboxProfile(workdir=tmp_path))
        assert argv[0] == "bwrap"
        i = argv.index("--ro-bind")
        assert argv[i + 1 : i + 3] == ["/", "/"]
        j = argv.index("--bind")
        assert argv[j + 1 : j + 3] == [str(tmp_path), str(tmp_path)]
        assert "--unshare-all" in argv
        assert "--die-with-parent" in argv
        assert "--share-net" not in argv  # red OFF por defecto

    def test_net_is_separate_permission(self, tmp_path: Path) -> None:
        argv = build_bwrap_argv(SandboxProfile(workdir=tmp_path, net=True))
        assert "--share-net" in argv

    def test_wrap_returns_shell_line(self, tmp_path: Path) -> None:
        import shlex

        cmd = "echo 'hola mundo'"
        wrapped = wrap_command(cmd, SandboxProfile(workdir=tmp_path))
        if wrapped is None:  # sin bwrap → contrato de degradación
            pytest.skip("bwrap no instalado")
        assert wrapped.startswith("bwrap ")
        # cola exacta: -- /bin/sh -c <cmd citado con shlex> (semántica, no texto crudo)
        assert wrapped.endswith(f"-- /bin/sh -c {shlex.quote(cmd)}")

    def test_wrap_none_without_bwrap(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sb.shutil, "which", lambda _: None)
        assert wrap_command("echo x", SandboxProfile(workdir=tmp_path)) is None


@require_bwrap
class TestJailReal:
    async def test_escape_write_outside_workdir_fails(self, tmp_path: Path) -> None:
        reg = Registry(make_tools(tmp_path, sandbox=True))
        res = await reg.execute("terminal", {"command": "touch /tmp/fuga_b3"}, "c1")
        assert "[exit 1]" in res.content
        assert "Read-only file system" in res.content
        assert not Path("/tmp/fuga_b3").exists()  # la fuga NO ocurrió

    async def test_write_inside_workdir_ok(self, tmp_path: Path) -> None:
        reg = Registry(make_tools(tmp_path, sandbox=True))
        res = await reg.execute("terminal", {"command": "echo dato > f.txt"}, "c1")
        assert "[exit 0]" in res.content
        assert (tmp_path / "f.txt").read_text() == "dato\n"

    async def test_home_outside_workdir_readonly(self, tmp_path: Path) -> None:
        reg = Registry(make_tools(tmp_path, sandbox=True))
        res = await reg.execute("terminal", {"command": f"touch {Path.home()}/fuga_b3_home"}, "c1")
        assert "[exit 1]" in res.content
        assert not (Path.home() / "fuga_b3_home").exists()

    async def test_network_off_by_default(self, tmp_path: Path) -> None:
        reg = Registry(make_tools(tmp_path, sandbox=True))
        res = await reg.execute(
            "terminal",
            {"command": "curl -s -m 4 -o /dev/null https://example.com; echo rc=$?"},
            "c1",
        )
        assert "rc=6" in res.content or "rc=7" in res.content  # DNS/conexión fallan

    async def test_network_permission_separate(self, tmp_path: Path) -> None:
        reg = Registry(make_tools(tmp_path, sandbox=True, sandbox_net=True))
        res = await reg.execute(
            "terminal",
            {"command": "curl -s -m 8 -o /dev/null -w %{http_code} https://example.com"},
            "c1",
        )
        assert "[exit 0]" in res.content and "200" in res.content


class TestDegradacionHonesta:
    async def test_note_when_bwrap_vanishes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tlamati.tools.terminal as tt

        monkeypatch.setattr(tt, "wrap_command", lambda cmd, profile: None)
        reg = Registry(make_tools(tmp_path, sandbox=True))
        res = await reg.execute("terminal", {"command": "echo sinjaula"}, "c1")
        assert "sin sandbox" in res.content  # nota visible, nunca silencio
        assert "sinjaula" in res.content

    async def test_sandbox_off_runs_plain(self, tmp_path: Path) -> None:
        reg = Registry(make_tools(tmp_path, sandbox=False))
        res = await reg.execute("terminal", {"command": "echo libre"}, "c1")
        assert res.content == "[exit 0]\nlibre"
        assert "sin sandbox" not in res.content
