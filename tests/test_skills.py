"""Tests for C3 skills: SKILL.md parsing, catalog stability, skill_view tool,
hermes-library compatibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from tlamati.memory.skills import (
    Skill,
    SkillLibrary,
    default_skill_roots,
    hermes_skill_root,
    make_skill_tools,
    parse_skill,
)


def _make_skill(
    root: Path, name: str, desc: str = "Una skill de prueba", category: str = ""
) -> Path:
    d = root / category / name if category else root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n\nCuerpo de la skill.\n",
        encoding="utf-8",
    )
    return d


@pytest.fixture
def lib_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    return root


class TestParsing:
    def test_parse_valid(self, lib_root: Path) -> None:
        d = _make_skill(lib_root, "deploy")
        sk = parse_skill(d / "SKILL.md")
        assert sk is not None
        assert sk.name == "deploy"
        assert sk.description == "Una skill de prueba"
        assert sk.dir == d

    def test_parse_missing_frontmatter_is_none(self, lib_root: Path) -> None:
        d = lib_root / "rota"
        d.mkdir()
        (d / "SKILL.md").write_text("sin frontmatter\n", encoding="utf-8")
        assert parse_skill(d / "SKILL.md") is None

    def test_parse_bad_yaml_is_none(self, lib_root: Path) -> None:
        d = lib_root / "mala"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: [roto\n---\n", encoding="utf-8")
        assert parse_skill(d / "SKILL.md") is None

    def test_parse_missing_name_is_none(self, lib_root: Path) -> None:
        d = lib_root / "sin_nombre"
        d.mkdir()
        (d / "SKILL.md").write_text("---\ndescription: x\n---\n", encoding="utf-8")
        assert parse_skill(d / "SKILL.md") is None


class TestLibrary:
    def test_scan_flat_and_nested(self, lib_root: Path) -> None:
        _make_skill(lib_root, "alpha")
        _make_skill(lib_root, "beta", category="devops")
        lib = SkillLibrary([lib_root])
        names = [s.name for s in lib.catalog()]
        assert names == ["alpha", "beta"]
        beta = lib.get("beta")
        assert beta is not None
        assert beta.category == "devops"

    def test_missing_root_skipped(self, lib_root: Path, tmp_path: Path) -> None:
        _make_skill(lib_root, "alpha")
        lib = SkillLibrary([tmp_path / "no-existe", lib_root])
        assert [s.name for s in lib.catalog()] == ["alpha"]

    def test_first_root_wins_on_duplicate(self, lib_root: Path, tmp_path: Path) -> None:
        root2 = tmp_path / "skills2"
        root2.mkdir()
        _make_skill(lib_root, "deploy", desc="proyecto")
        _make_skill(root2, "deploy", desc="usuario")
        lib = SkillLibrary([lib_root, root2])
        deploy = lib.get("deploy")
        assert deploy is not None
        assert deploy.description == "proyecto"

    def test_catalog_text_is_stable_order(self, lib_root: Path) -> None:
        _make_skill(lib_root, "zeta")
        _make_skill(lib_root, "alfa")
        lib = SkillLibrary([lib_root])
        t1 = lib.catalog_text()
        t2 = lib.catalog_text()
        assert t1 == t2  # byte-stable → prefix cache intact
        assert t1.index("alfa") < t1.index("zeta")

    def test_hidden_dirs_skipped(self, lib_root: Path) -> None:
        """hermes compat: .archive/ holds retired skills — never inject them."""
        _make_skill(lib_root, "activa")
        _make_skill(lib_root, "jubilada", category=".archive")
        lib = SkillLibrary([lib_root])
        assert [s.name for s in lib.catalog()] == ["activa"]

    def test_rescan_picks_up_new(self, lib_root: Path) -> None:
        lib = SkillLibrary([lib_root])
        assert lib.catalog() == []
        _make_skill(lib_root, "nueva")
        lib.rescan()
        assert [s.name for s in lib.catalog()] == ["nueva"]


class TestSkillTools:
    async def test_skill_view_body_and_linked(self, lib_root: Path) -> None:
        d = _make_skill(lib_root, "deploy")
        (d / "references").mkdir()
        (d / "references" / "api.md").write_text("# API\nendpoints", encoding="utf-8")
        lib = SkillLibrary([lib_root])
        view = next(t for t in make_skill_tools(lib) if t.name == "skill_view")
        out = await view.run({"name": "deploy"})
        assert "Cuerpo de la skill" in out
        assert "references/api.md" in out  # linked inventory shown
        out2 = await view.run({"name": "deploy", "file_path": "references/api.md"})
        assert "endpoints" in out2

    async def test_skill_view_unknown_is_honest(self, lib_root: Path) -> None:
        _make_skill(lib_root, "deploy")
        lib = SkillLibrary([lib_root])
        view = next(t for t in make_skill_tools(lib) if t.name == "skill_view")
        out = await view.run({"name": "nope"})
        assert out.startswith("ERROR")
        assert "deploy" in out  # suggests what exists

    async def test_skill_view_empty_library_is_honest(self, tmp_path: Path) -> None:
        """E3d bug menor: con la librería vacía el error decía 'Disponibles: '
        (nada). Ahora explica que no hay raíces configuradas + hint del flag."""
        lib = SkillLibrary([tmp_path / "inexistente"])
        view = next(t for t in make_skill_tools(lib) if t.name == "skill_view")
        out = await view.run({"name": "cualquiera"})
        assert out.startswith("ERROR")
        assert "Disponibles: " not in out
        assert "--skills-dir" in out  # hint accionable

    async def test_skill_view_path_escape_blocked(self, lib_root: Path, tmp_path: Path) -> None:
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP SECRET", encoding="utf-8")
        _make_skill(lib_root, "deploy")
        lib = SkillLibrary([lib_root])
        view = next(t for t in make_skill_tools(lib) if t.name == "skill_view")
        out = await view.run({"name": "deploy", "file_path": "../../secret.txt"})
        assert out.startswith("ERROR")
        assert "TOP SECRET" not in out

    async def test_skill_list_tool(self, lib_root: Path) -> None:
        _make_skill(lib_root, "deploy")
        lib = SkillLibrary([lib_root])
        lst = next(t for t in make_skill_tools(lib) if t.name == "skill_list")
        out = await lst.run({})
        assert "deploy" in out and "(1 skills)" in out

    def test_tools_are_auto_and_not_untrusted(self, lib_root: Path) -> None:
        from tlamati.tools.registry import Permission

        lib = SkillLibrary([lib_root])
        for t in make_skill_tools(lib):
            assert t.permission == Permission.AUTO
            assert not t.produces_untrusted  # local read-only, re-fetchable


class TestRootsAndHermesCompat:
    def test_default_roots_order(self, tmp_path: Path) -> None:
        roots = default_skill_roots(tmp_path, [Path("/extra")])
        assert roots[0] == tmp_path / ".tlamati" / "skills"
        assert Path("/extra") in roots
        # E3d: extra va ANTES de hermes; hermes (si existe) siempre al final.
        if hermes_skill_root().is_dir():
            assert roots[-1] == hermes_skill_root()
            assert roots.index(Path("/extra")) < len(roots) - 1
        else:
            assert roots[-1] == Path("/extra")

    def test_hermes_root_appended_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = tmp_path / "home"
        hermes_dir = fake_home / ".hermes" / "skills"
        hermes_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        roots = default_skill_roots(tmp_path / "proj")
        assert roots[-1] == hermes_dir  # ceremonia cero: siempre al final

    def test_hermes_root_absent_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = tmp_path / "home-sin-hermes"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        roots = default_skill_roots(tmp_path / "proj", [Path("/extra")])
        assert (fake_home / ".hermes" / "skills") not in roots
        assert roots[-1] == Path("/extra")  # orden pre-E3d intacto

    def test_reads_real_hermes_library_format(self, lib_root: Path) -> None:
        """Compat proof: a skill written EXACTLY like hermes writes them
        (frontmatter + tags + related_skills + body) parses without changes."""
        d = lib_root / "hermes-style"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\n"
            "name: hermes-style\n"
            "description: Formato real de hermes con campos extra.\n"
            "tags: [devops, ci]\n"
            "related_skills: []\n"
            "required_environment_variables: []\n"
            "---\n\n# Body\n\nPasos exactos.\n",
            encoding="utf-8",
        )
        lib = SkillLibrary([lib_root])
        sk: Skill | None = lib.get("hermes-style")
        assert sk is not None
        assert "Formato real" in sk.description
