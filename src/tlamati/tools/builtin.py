"""Built-in toolset composition (B2): files + search + terminal.

``make_tools(workdir)`` returns the full formal toolset. Order is stable
(read, write, edit, search, terminal) because tool specs are part of the
cacheable prefix ("caching is sacred").
"""

from __future__ import annotations

from pathlib import Path

from tlamati.tools.files import make_file_tools
from tlamati.tools.registry import Tool
from tlamati.tools.search import make_search_tools
from tlamati.tools.terminal import make_terminal_tools


def make_tools(workdir: Path) -> list[Tool]:
    """Build the built-in toolset pinned to ``workdir``."""
    return [
        *make_file_tools(workdir),
        *make_search_tools(workdir),
        *make_terminal_tools(workdir),
    ]
