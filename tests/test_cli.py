"""CLI smoke tests."""

from __future__ import annotations

import pytest

from tlamati import __version__
from tlamati.cli import main


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_prompt_stub_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-p", "arregla X"]) == 2
    assert "A4" in capsys.readouterr().err


def test_no_args_exits_0() -> None:
    assert main([]) == 0
