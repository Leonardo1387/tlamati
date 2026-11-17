"""Tests for C4 instructions loader: AGENTS.md/CLAUDE.md discovery, merge
order, repo boundary, version hash, global file."""

from __future__ import annotations

from pathlib import Path

import pytest

from tlamati.context.instructions import (
    Instructions,
    load_instructions,
    render_for_prompt,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fake git repo root."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    return root


class TestDiscovery:
    def test_no_files_no_block(self, repo: Path) -> None:
        instr = load_instructions(repo, include_global=False)
        assert not instr.found
        assert instr.block == ""
        assert instr.version == ""
        assert render_for_prompt(instr) == ""

    def test_agents_md_found(self, repo: Path) -> None:
        (repo / "AGENTS.md").write_text("# Reglas\nNo romper main.", encoding="utf-8")
        instr = load_instructions(repo, include_global=False)
        assert instr.found
        assert "No romper main" in instr.block
        assert len(instr.sources) == 1

    def test_claude_md_compat(self, repo: Path) -> None:
        """A Claude Code repo (CLAUDE.md only) instructs tlamati unchanged."""
        (repo / "CLAUDE.md").write_text("Usa español mexicano.", encoding="utf-8")
        instr = load_instructions(repo, include_global=False)
        assert instr.found
        assert "español mexicano" in instr.block

    def test_agents_md_wins_over_claude_md_same_dir(self, repo: Path) -> None:
        (repo / "AGENTS.md").write_text("regla AGENTS", encoding="utf-8")
        (repo / "CLAUDE.md").write_text("regla CLAUDE", encoding="utf-8")
        instr = load_instructions(repo, include_global=False)
        assert "regla AGENTS" in instr.block
        assert "regla CLAUDE" not in instr.block


class TestMergeOrder:
    def test_global_first_then_repo(self, repo: Path, tmp_path: Path) -> None:
        g = tmp_path / "global-AGENTS.md"
        g.write_text("GLOBAL: sé breve", encoding="utf-8")
        (repo / "AGENTS.md").write_text("REPO: usa pytest", encoding="utf-8")
        instr = load_instructions(repo, global_path=g, include_global=True)
        assert instr.block.index("GLOBAL") < instr.block.index("REPO")

    def test_deeper_refines_outer(self, repo: Path) -> None:
        sub = repo / "packages" / "core"
        sub.mkdir(parents=True)
        (repo / "AGENTS.md").write_text("RAIZ: regla general", encoding="utf-8")
        (sub / "AGENTS.md").write_text("SUBMODULO: regla fina", encoding="utf-8")
        instr = load_instructions(sub, include_global=False)
        assert len(instr.sources) == 2
        assert instr.block.index("RAIZ") < instr.block.index("SUBMODULO")

    def test_walk_stops_at_repo_boundary(self, repo: Path, tmp_path: Path) -> None:
        """An AGENTS.md ABOVE the .git boundary must NOT leak into the run."""
        (tmp_path / "AGENTS.md").write_text("FUERA DEL REPO", encoding="utf-8")
        (repo / "AGENTS.md").write_text("DENTRO DEL REPO", encoding="utf-8")
        instr = load_instructions(repo, include_global=False)
        assert "DENTRO" in instr.block
        assert "FUERA" not in instr.block

    def test_no_git_boundary_stops_at_fs_root(self, tmp_path: Path) -> None:
        """Without .git the walk goes up; a stray ancestor file IS collected
        (codex behaviour: no repo = no boundary). Test with a shallow tree."""
        d = tmp_path / "a" / "b"
        d.mkdir(parents=True)
        (tmp_path / "a" / "AGENTS.md").write_text("ancestro", encoding="utf-8")
        instr = load_instructions(d, include_global=False)
        assert "ancestro" in instr.block


class TestVersioning:
    def test_version_is_content_hash_stable(self, repo: Path) -> None:
        (repo / "AGENTS.md").write_text("regla", encoding="utf-8")
        v1 = load_instructions(repo, include_global=False)
        v2 = load_instructions(repo, include_global=False)
        assert v1.version == v2.version
        assert len(v1.version) == 12

    def test_version_changes_with_content(self, repo: Path) -> None:
        f = repo / "AGENTS.md"
        f.write_text("v1", encoding="utf-8")
        a = load_instructions(repo, include_global=False)
        f.write_text("v2", encoding="utf-8")
        b = load_instructions(repo, include_global=False)
        assert a.version != b.version

    def test_render_contains_version_marker(self, repo: Path) -> None:
        (repo / "AGENTS.md").write_text("regla", encoding="utf-8")
        instr = load_instructions(repo, include_global=False)
        out = render_for_prompt(instr)
        assert f"v:{instr.version}" in out
        assert "INSTRUCCIONES DEL PROYECTO" in out

    def test_empty_file_yields_no_block(self, repo: Path) -> None:
        (repo / "AGENTS.md").write_text("   \n", encoding="utf-8")
        instr = load_instructions(repo, include_global=False)
        assert not instr.found

    def test_unreadable_file_skipped_honestly(self, repo: Path) -> None:
        (repo / "AGENTS.md").write_text("regla buena", encoding="utf-8")
        bad = repo / "CLAUDE.md"
        bad.write_text("x", encoding="utf-8")
        bad.chmod(0o000)
        try:
            instr = load_instructions(repo, include_global=False)
            # AGENTS.md wins in same dir anyway; assert no crash + content
            assert "regla buena" in instr.block
        finally:
            bad.chmod(0o644)


class TestFrozenDataclass:
    def test_instructions_is_frozen(self) -> None:
        import dataclasses

        instr = Instructions(sources=(), block="", version="")
        with pytest.raises(dataclasses.FrozenInstanceError):
            instr.block = "mutado"  # type: ignore[misc]
