"""NIVEL 2f — advisory pre-commit (dogfood #6).

Si hay diff staged que toca archivos que el AGENTS.md del repo marca como
"compartido/crítico", recordatorio de no-regresión tras git add/commit.
Advisory = MENSAJE, NUNCA bloqueo (filosofía M8: advisory no muta).

Tests con repos git REALES en tmp_path (git init) — sin mocks del índice.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tlamati.context.late_instructions import (
    LateInstructions,
    critical_paths_from_instructions,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git no está instalado"
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        env={
            "HOME": str(root.parent),
            "PATH": "/usr/bin:/bin",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


class TestCriticalPathsParsing:
    def test_linea_con_marcador_aporta_rutas(self) -> None:
        text = "El directorio datos/comunes/ es COMPARTIDO entre pasos."
        rutas = critical_paths_from_instructions(text)
        assert "datos/comunes" in rutas

    def test_sin_marcador_sin_rutas(self) -> None:
        text = "Usa pytest para correr los tests.\nCommits en español."
        assert critical_paths_from_instructions(text) == set()

    def test_archivo_individual_marcado(self) -> None:
        text = "- validador.py es crítico: no romper su contrato."
        assert "validador.py" in critical_paths_from_instructions(text)

    def test_acento_variante(self) -> None:
        text = "src/core.py es critico para la corrida"
        assert "src/core.py" in critical_paths_from_instructions(text)


class TestCommitAdvisory:
    def test_staged_critico_genera_advisory(self, git_repo: Path) -> None:
        (git_repo / "AGENTS.md").write_text(
            "# Reglas\ndatos/comunes/ es COMPARTIDO — no-regresión obligatoria.\n",
            encoding="utf-8",
        )
        comun = git_repo / "datos" / "comunes"
        comun.mkdir(parents=True)
        (comun / "x.txt").write_text("cambio", encoding="utf-8")
        _git(git_repo, "add", "datos/comunes/x.txt")
        li = LateInstructions(git_repo)
        texto = li.reminder("terminal", {"command": "git commit -m cambio"})
        assert texto is not None
        assert "ADVISORY PRE-COMMIT" in texto
        assert "datos/comunes/x.txt" in texto

    def test_staged_sin_critico_silencio(self, git_repo: Path) -> None:
        (git_repo / "AGENTS.md").write_text(
            "datos/comunes/ es COMPARTIDO.\n", encoding="utf-8"
        )
        (git_repo / "otro.py").write_text("x = 1", encoding="utf-8")
        _git(git_repo, "add", "otro.py")
        li = LateInstructions(git_repo)
        assert li.reminder("terminal", {"command": "git add otro.py"}) is None

    def test_sin_git_commit_silencio(self, git_repo: Path) -> None:
        (git_repo / "AGENTS.md").write_text(
            "datos/ es COMPARTIDO.\n", encoding="utf-8"
        )
        (git_repo / "datos").mkdir()
        (git_repo / "datos" / "a.txt").write_text("v", encoding="utf-8")
        _git(git_repo, "add", "datos/a.txt")
        li = LateInstructions(git_repo)
        # git status NO es add/commit → sin advisory
        assert li.reminder("terminal", {"command": "git status"}) is None

    def test_repo_sin_agents_md_silencio(self, git_repo: Path) -> None:
        (git_repo / "a.txt").write_text("v", encoding="utf-8")
        _git(git_repo, "add", "a.txt")
        li = LateInstructions(git_repo)
        assert li.reminder("terminal", {"command": "git commit -m x"}) is None

    def test_agents_md_sin_marcadores_silencio(self, git_repo: Path) -> None:
        (git_repo / "AGENTS.md").write_text("Usa pytest.\n", encoding="utf-8")
        (git_repo / "a.txt").write_text("v", encoding="utf-8")
        _git(git_repo, "add", "a.txt")
        li = LateInstructions(git_repo)
        assert li.reminder("terminal", {"command": "git commit -m x"}) is None

    def test_advisory_con_cd_a_otro_repo(self, git_repo: Path, tmp_path: Path) -> None:
        """El advisory sigue al repo del cd (mismo mecanismo que 1a)."""
        (git_repo / "AGENTS.md").write_text(
            "src/ es COMPARTIDO.\n", encoding="utf-8"
        )
        (git_repo / "src").mkdir()
        (git_repo / "src" / "m.py").write_text("v", encoding="utf-8")
        _git(git_repo, "add", "src/m.py")
        li = LateInstructions(tmp_path)  # workdir fuera del repo
        texto = li.reminder(
            "terminal", {"command": f"cd {git_repo} && git add src/m.py"}
        )
        assert texto is not None and "src/m.py" in texto

    async def test_no_bloquea_el_comando(self, git_repo: Path) -> None:
        """Filosofía M8: el advisory es contenido adjunto; el tool result
        original (éxito del commit) no se toca — verificado a nivel Registry."""
        from tlamati.tools.registry import Registry, Tool

        (git_repo / "AGENTS.md").write_text("a.txt es crítico.\n", encoding="utf-8")
        (git_repo / "a.txt").write_text("v", encoding="utf-8")
        _git(git_repo, "add", "a.txt")

        async def terminal(args: dict) -> str:
            return "[exit 0]"

        schema = {"type": "object", "properties": {}, "required": []}
        registry = Registry(
            [Tool(name="terminal", description="", input_schema=schema, run=terminal)],
            late_instructions=LateInstructions(git_repo),
        )
        result = await registry.execute("terminal", {"command": "git commit -m x"}, "t1")
        assert not result.is_error  # NUNCA bloqueo
        assert result.content.startswith("[exit 0]")
        assert "ADVISORY PRE-COMMIT" in result.content
