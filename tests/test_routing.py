"""Tests C6 — routing.md (workspaces): parser de tabla, resolución de
workspace, versión hash estable, fail-soft, integración de prefijo."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from tlamati.context.budget import Budget
from tlamati.context.routing import (
    Routing,
    Workspace,
    load_routing,
    parse_routing_table,
    render_for_prompt,
    resolve_workspace,
)
from tlamati.core.loop import run_loop
from tlamati.core.messages import Event, Message, MessageEnd, TextDelta, Usage
from tlamati.memory.skills import SkillLibrary
from tlamati.providers.base import ToolSpec
from tlamati.tools.registry import Registry

VALID_TABLE = """\
# Routing del proyecto

Texto libre antes de la tabla (el parser lo ignora).

| patrón | workspace | contexto | cargar | omitir | skills |
|---|---|---|---|---|---|
| *docs* | documentacion | docs/contexto.md | docs/*.md | src/, tests/ | escribir-docs |
| *bug* | codigo | src/contexto.md | src/ | vendor/ | depurar, testear |

Notas al pie también ignoradas.
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".tlamati").mkdir(parents=True)
    (root / ".git").mkdir()
    return root


def _write(root: Path, table: str) -> Path:
    f = root / ".tlamati" / "routing.md"
    f.write_text(table, encoding="utf-8")
    return f


class TestParser:
    def test_parse_valid_table(self) -> None:
        wss = parse_routing_table(VALID_TABLE)
        assert len(wss) == 2
        docs = wss[0]
        assert docs.name == "documentacion"
        assert docs.pattern == "*docs*"
        assert docs.context_file == "docs/contexto.md"
        assert docs.load == ("docs/*.md",)
        assert docs.omit == ("src/", "tests/")
        assert docs.skills == ("escribir-docs",)

    def test_semicolon_separator(self) -> None:
        wss = parse_routing_table("| tarea | zona | omitir |\n|-|-|-|\n| x | a | p; q |\n")
        assert wss[0].omit == ("p", "q")

    def test_missing_required_header_ignored(self) -> None:
        assert parse_routing_table("| foo | bar |\n|-|-|\n| a | b |\n") == ()

    def test_row_missing_name_skipped(self) -> None:
        wss = parse_routing_table("| patrón | workspace |\n|-|-|\n| *x* |  |\n| *y* | buena |\n")
        assert len(wss) == 1
        assert wss[0].name == "buena"

    def test_malformed_row_length_skipped(self) -> None:
        wss = parse_routing_table(
            "| patrón | workspace |\n|-|-|\n| solo-una-celda |\n| *y* | ok |\n"
        )
        assert [w.name for w in wss] == ["ok"]

    def test_prose_only_no_table(self) -> None:
        assert parse_routing_table("# Hola\n\nnada de tablas aquí\n") == ()


class TestResolution:
    def test_first_match_wins(self) -> None:
        wss = (
            Workspace(name="a", pattern="*x*"),
            Workspace(name="b", pattern="*x*y*"),
        )
        ws, err = resolve_workspace(wss, task="arregla x y")
        assert ws is not None and ws.name == "a"
        assert err == ""

    def test_no_match_returns_none(self) -> None:
        ws, err = resolve_workspace((Workspace(name="a", pattern="*docs*"),), task="fix bug")
        assert ws is None
        assert err == ""

    def test_forced_flag_beats_task(self) -> None:
        wss = (Workspace(name="a", pattern="*docs*"), Workspace(name="b", pattern="*bug*"))
        ws, _ = resolve_workspace(wss, task="escribe docs", forced="b")
        assert ws is not None and ws.name == "b"

    def test_forced_unknown_honest_error(self) -> None:
        ws, err = resolve_workspace((Workspace(name="a", pattern="*"),), forced="zzz")
        assert ws is None
        assert "zzz" in err and "a" in err

    def test_case_insensitive_match(self) -> None:
        ws, _ = resolve_workspace((Workspace(name="a", pattern="*DOCS*"),), task="mis Docs")
        assert ws is not None


class TestLoadRouting:
    def test_no_file_empty_routing(self, repo: Path) -> None:
        r = load_routing(repo)
        assert not r.found
        assert render_for_prompt(r) == ""  # prefijo byte-idéntico a pre-C6

    def test_load_valid(self, repo: Path) -> None:
        _write(repo, VALID_TABLE)
        r = load_routing(repo, task="actualizar docs")
        assert r.found
        assert len(r.workspaces) == 2
        assert r.active is not None and r.active.name == "documentacion"

    def test_stops_at_git_boundary(self, repo: Path, tmp_path: Path) -> None:
        _write(repo, VALID_TABLE)
        outside = tmp_path / ".tlamati"
        outside.mkdir()
        (outside / "routing.md").write_text("| patrón | workspace |\n|-|-|\n| * | fuera |\n")
        r = load_routing(repo)
        assert all(w.name != "fuera" for w in r.workspaces)

    def test_broken_table_fail_soft(self, repo: Path) -> None:
        _write(repo, "# routing\n\nse me olvidó la tabla :(\n")
        r = load_routing(repo)
        assert not r.found
        assert r.error  # honest note, never raises
        assert render_for_prompt(r) == ""

    def test_unreadable_file_fail_soft(self, repo: Path) -> None:
        f = _write(repo, VALID_TABLE)
        f.chmod(0o000)
        try:
            r = load_routing(repo)
            assert not r.found
            assert "no legible" in r.error
        finally:
            f.chmod(0o644)

    def test_version_stable_and_content_hash(self, repo: Path) -> None:
        f = _write(repo, VALID_TABLE)
        v1 = load_routing(repo).version
        v2 = load_routing(repo).version
        assert v1 == v2 and len(v1) == 12
        # editar la tabla (fila nueva DENTRO de ella) cambia la versión
        f.write_text(
            VALID_TABLE.replace(
                "| *bug* | codigo | src/contexto.md | src/ | vendor/ | depurar, testear |",
                "| *bug* | codigo | src/contexto.md | src/ | vendor/ | depurar, testear |\n"
                "| *nuevo* | otro | | | | |",
            ),
            encoding="utf-8",
        )
        v3 = load_routing(repo).version
        assert v3 != v1
        assert len(load_routing(repo).workspaces) == 3

    def test_context_file_injected_only_for_active(self, repo: Path) -> None:
        _write(repo, VALID_TABLE)
        docs = repo / "docs"
        docs.mkdir()
        (docs / "contexto.md").write_text("REGLAS-DE-DOCS únicas", encoding="utf-8")
        src = repo / "src"
        src.mkdir()
        (src / "contexto.md").write_text("REGLAS-DE-SRC únicas", encoding="utf-8")
        r_docs = load_routing(repo, task="escribir docs")
        r_code = load_routing(repo, task="fix bug en parser")
        assert "REGLAS-DE-DOCS" in r_docs.context_block
        assert "REGLAS-DE-SRC" not in r_docs.context_block
        assert "REGLAS-DE-SRC" in r_code.context_block

    def test_context_missing_file_fail_soft(self, repo: Path) -> None:
        _write(repo, VALID_TABLE)
        r = load_routing(repo, task="docs")  # docs/contexto.md no existe
        assert r.active is not None
        assert r.context_block == ""
        assert "no legible" in r.error

    def test_context_path_escape_blocked(self, repo: Path, tmp_path: Path) -> None:
        (tmp_path / "secreto.md").write_text("FUERA-DEL-REPO", encoding="utf-8")
        _write(
            repo,
            "| patrón | workspace | contexto |\n|-|-|-|\n| * | a | ../secreto.md |\n",
        )
        r = load_routing(repo, task="x")
        assert r.context_block == ""
        assert "fuera del proyecto" in r.error


class TestRender:
    def test_render_contains_map_and_active_only(self, repo: Path) -> None:
        _write(repo, VALID_TABLE)
        r = load_routing(repo, task="docs")
        out = render_for_prompt(r)
        assert f"v:{r.version}" in out
        assert "documentacion" in out
        # layer-1 MAPA = tabla completa: los DOS patrones visibles
        assert "*docs*" in out and "*bug*" in out
        # guía de la zona activa presente
        assert "OMITE" in out and "vendor/" not in out.split("OMITE")[1]

    def test_render_without_active_workspace(self, repo: Path) -> None:
        _write(repo, VALID_TABLE)
        r = load_routing(repo, task="nada que ver")
        out = render_for_prompt(r)
        assert "Ningún workspace activo" in out

    def test_empty_routing_renders_empty(self) -> None:
        r = Routing(
            source=None,
            project_root=None,
            workspaces=(),
            active=None,
            table="",
            context_block="",
            version="",
        )
        assert render_for_prompt(r) == ""


class TestCatalogFilter:
    def test_catalog_text_only_filters(self, tmp_path: Path) -> None:
        root = tmp_path / "skills"
        for name in ("alpha", "beta"):
            d = root / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: d-{name}\n---\ncuerpo\n",
                encoding="utf-8",
            )
        lib = SkillLibrary([root])
        full = lib.catalog_text()
        assert "alpha" in full and "beta" in full
        filtered = lib.catalog_text(only=("beta",))
        assert "beta" in filtered and "alpha" not in filtered
        assert lib.catalog_text(only=None) == full  # None = sin filtro (default)


class FakeProvider:
    """Scripted provider (patrón test_loop/test_plan_mode) — cero red."""

    model = "fake"

    def __init__(self) -> None:
        self.systems: list[str] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        for m in messages:
            if m.role == "system":
                self.systems.append(str(m.content))
        yield TextDelta(text="listo")
        yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=5, output_tokens=1))


class TestPrefixIntegration:
    async def test_prefix_carries_active_map_only(self, repo: Path) -> None:
        _write(repo, VALID_TABLE)
        docs = repo / "docs"
        docs.mkdir()
        (docs / "contexto.md").write_text("REGLAS-DE-DOCS únicas", encoding="utf-8")
        src = repo / "src"
        src.mkdir()
        (src / "contexto.md").write_text("REGLAS-DE-SRC únicas", encoding="utf-8")

        async def _run(task: str, workspace: str = "") -> str:
            r = load_routing(repo, task=task, workspace=workspace)
            provider = FakeProvider()
            await run_loop(
                provider,  # type: ignore[arg-type]
                system="BASE" + render_for_prompt(r),
                user_prompt=task,
                tools=Registry([]),
                budget=Budget(100_000),
                max_turns=1,
            )
            return provider.systems[0]

        sys_docs = await _run("escribir docs")
        assert "REGLAS-DE-DOCS" in sys_docs
        assert "REGLAS-DE-SRC" not in sys_docs
        assert "Workspace ACTIVO: documentacion" in sys_docs

        sys_code = await _run("fix bug")
        assert "REGLAS-DE-SRC" in sys_code
        assert "REGLAS-DE-DOCS" not in sys_code

        # forzado con flag: mapa igual, habitación cambiada
        sys_forced = await _run("escribir docs", workspace="codigo")
        assert "REGLAS-DE-SRC" in sys_forced

    async def test_no_routing_file_prefix_unchanged(self, repo: Path) -> None:
        provider = FakeProvider()
        r = load_routing(repo)
        await run_loop(
            provider,  # type: ignore[arg-type]
            system="BASE" + render_for_prompt(r),
            user_prompt="hola",
            tools=Registry([]),
            budget=Budget(100_000),
            max_turns=1,
        )
        assert provider.systems[0] == "BASE"  # byte-idéntico (cache sagrada)
