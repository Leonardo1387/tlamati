"""B2 — file/search/terminal tools: fuzzy ladder, pagination, rg integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from tlamati.tools.builtin import make_tools
from tlamati.tools.files import fuzzy_replace, render_lines
from tlamati.tools.registry import Registry


@pytest.fixture
def reg(tmp_path: Path) -> Registry:
    return Registry(make_tools(tmp_path))


class TestToolsetShape:
    def test_five_tools_stable_order(self, reg: Registry) -> None:
        names = [s.name for s in reg.specs()]
        assert names == ["read_file", "write_file", "edit", "search_files", "terminal"]

    def test_only_terminal_sandboxable(self, reg: Registry) -> None:
        flags = {t.name: t.sandboxable for t in reg}
        assert flags == {
            "read_file": False,
            "write_file": False,
            "edit": False,
            "search_files": False,
            "terminal": True,
        }


class TestRenderLines:
    def test_numbering_and_pagination(self) -> None:
        text = "\n".join(f"l{i}" for i in range(1, 11))
        out = render_lines(text, 3, 2)
        assert out.splitlines()[0] == "3|l3"
        assert out.splitlines()[1] == "4|l4"
        assert "next offset=5" in out

    def test_no_pagination_note_when_complete(self) -> None:
        out = render_lines("a\nb", 1, 500)
        assert "1|a" in out and "next offset" not in out


class TestFuzzyLadder:
    TEXT = 'def foo():\n    return 42\n\ndef bar():\n    return 43\n'

    def test_s1_exact(self) -> None:
        out, strat = fuzzy_replace(self.TEXT, "return 42", "return 0")
        assert "return 0" in out and strat.startswith("S1")

    def test_s2_trailing_whitespace(self) -> None:
        out, strat = fuzzy_replace(self.TEXT, "return 42   ", "return 0")
        assert "return 0" in out and strat.startswith("S2")

    def test_indentation_difference(self) -> None:
        # old trae MÁS indent que el archivo → S1 literal no encuentra
        out, strat = fuzzy_replace(self.TEXT, "        return 42", "return 0")
        assert "return 0" in out and strat == "S3 lstrip"

    def test_stripped_lines(self) -> None:
        out, strat = fuzzy_replace(self.TEXT, "def foo():\nreturn 42", "def foo():\n    return 0")
        assert "return 0" in out and strat != "S1 exact"

    def test_blank_line_difference(self) -> None:
        text = "a = 1\n\n\nb = 2\n"
        out, strat = fuzzy_replace(text, "a = 1\n\nb = 2", "c = 3")
        assert "c = 3" in out and strat != "S1 exact"

    def test_crlf_file_lf_needle(self) -> None:
        text = "line one\r\nline two\r\n"
        out, strat = fuzzy_replace(text, "line one\nline two", "replaced")
        assert "replaced" in out and strat == "S6 crlf-normalized"

    def test_s8_anchored_tolerates_inserted_lines(self) -> None:
        # el archivo tiene líneas EXTRA entre las líneas de old → S8 anclado
        text = "header\nalpha\nEXTRA1\nEXTRA2\nbeta\nfooter\n"
        out, strat = fuzzy_replace(text, "header\nalpha\nbeta\nfooter", "REPLACED BLOCK")
        assert out.startswith("REPLACED BLOCK") and strat == "S8 anchored-fuzzy"

    def test_s9_token_subsequence(self) -> None:
        text = "the   quick brown\nfox jumps\n"
        out, strat = fuzzy_replace(text, "quick brown fox", "slow turtle")
        assert "slow turtle" in out and strat.startswith("S9")

    def test_no_match_honest_error(self) -> None:
        with pytest.raises(ValueError, match="no strategy matched"):
            fuzzy_replace(self.TEXT, "return 99", "x")

    def test_ambiguous_match_refuses(self) -> None:
        text = "dup\ndup\n"
        with pytest.raises(ValueError, match="2 matches"):
            fuzzy_replace(text, "dup", "one")

    def test_replace_all(self) -> None:
        text = "dup\ndup\n"
        out, _ = fuzzy_replace(text, "dup", "one", replace_all=True)
        assert out == "one\none\n"

    def test_empty_old_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            fuzzy_replace(self.TEXT, "", "x")

    def test_noop_edit_rejected(self) -> None:
        with pytest.raises(ValueError, match="identical"):
            fuzzy_replace(self.TEXT, "return 42", "return 42")


class TestEditTool:
    async def test_edit_roundtrip(self, reg: Registry, tmp_path: Path) -> None:
        (tmp_path / "f.py").write_text("x = 42\n")
        args = {"path": "f.py", "old_string": "42", "new_string": "0"}
        res = await reg.execute("edit", args, "c1")
        assert not res.is_error and "strategy S1" in res.content
        assert (tmp_path / "f.py").read_text() == "x = 0\n"

    async def test_edit_missing_file(self, reg: Registry) -> None:
        res = await reg.execute(
            "edit", {"path": "ghost.py", "old_string": "a", "new_string": "b"}, "c1"
        )
        assert res.is_error and "no such file" in res.content

    async def test_edit_bad_args_schema(self, reg: Registry) -> None:
        res = await reg.execute("edit", {"path": "x.py"}, "c1")  # faltan obligatorios
        assert res.is_error and "invalid arguments" in res.content

    async def test_edit_delete_with_empty_new(self, reg: Registry, tmp_path: Path) -> None:
        (tmp_path / "f.txt").write_text("keep\nDROP\nkeep2\n")
        res = await reg.execute(
            "edit", {"path": "f.txt", "old_string": "DROP\n", "new_string": ""}, "c1"
        )
        assert not res.is_error
        assert (tmp_path / "f.txt").read_text() == "keep\nkeep2\n"


class TestReadTool:
    async def test_read_pagination_args(self, reg: Registry, tmp_path: Path) -> None:
        (tmp_path / "big.txt").write_text("\n".join(f"l{i}" for i in range(1, 101)))
        res = await reg.execute("read_file", {"path": "big.txt", "offset": 10, "limit": 5}, "c1")
        assert not res.is_error
        assert res.content.startswith("10|l10")
        assert "14|l14" in res.content and "15|l15" not in res.content


class TestSearchTool:
    async def test_content_search(self, reg: Registry, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("def needle():\n    pass\n")
        (tmp_path / "b.txt").write_text("nothing here\n")
        res = await reg.execute(
            "search_files", {"pattern": "needle", "target": "content"}, "c1"
        )
        assert not res.is_error
        assert "a.py:1" in res.content and "b.txt" not in res.content

    async def test_content_no_matches_honest(self, reg: Registry, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        res = await reg.execute("search_files", {"pattern": "zzz_no_existe"}, "c1")
        assert not res.is_error and res.content == "(no matches)"

    async def test_bad_regex_surfaces_rg_error(self, reg: Registry) -> None:
        res = await reg.execute("search_files", {"pattern": "(unclosed"}, "c1")
        assert res.is_error and "rg exit 2" in res.content

    async def test_files_mode_glob(self, reg: Registry, tmp_path: Path) -> None:
        (tmp_path / "x.py").write_text("")
        (tmp_path / "y.txt").write_text("")
        res = await reg.execute(
            "search_files", {"pattern": "*", "target": "files", "file_glob": "*.py"}, "c1"
        )
        assert not res.is_error and "x.py" in res.content and "y.txt" not in res.content

    async def test_missing_path(self, reg: Registry) -> None:
        res = await reg.execute("search_files", {"pattern": "x", "path": "/no/existe"}, "c1")
        assert res.is_error and "does not exist" in res.content


class TestTerminalTool:
    async def test_echo(self, reg: Registry) -> None:
        res = await reg.execute("terminal", {"command": "echo hola"}, "c1")
        assert "[exit 0]" in res.content and "hola" in res.content

    async def test_nonzero_exit_honest(self, reg: Registry) -> None:
        res = await reg.execute("terminal", {"command": "exit 3"}, "c1")
        assert "[exit 3]" in res.content and not res.is_error
