"""B2 — file tools: read_file, write_file, edit (fuzzy 9-strategy ladder).

read_file: line numbers, offset/limit pagination, honest truncation markers
(never silently drop content — M1 spout rule).

write_file: create-or-overwrite, parent dirs auto-created, reports bytes.

edit: find-and-replace with a fuzzy ladder (donor: hermes patch). Strategies
run STRICT → LENIENT; the first that yields exactly one match (or N matches
with replace_all) wins. If a lenient strategy would match MORE than once and
replace_all is off → honest ambiguity error, never a coin-flip pick.

The 9 strategies (each receives old_string + the file text, returns spans in
the ORIGINAL text):
  S1 exact literal match
  S2 trailing-whitespace tolerant (each line rstripped + "[ \t]*")
  S3 leading-indentation tolerant (each line lstripped, "\n[ \t]*" joins)
  S4 whitespace-collapsed (runs of spaces/tabs inside lines → "[ \t]+")
  S5 line-wise stripped (strip both ends, flexible-indent newlines)
  S6 CRLF/LF normalized (only fires when the file contains CRLF)
  S7 blank-line differences (extra/missing empty lines between matched lines)
  S8 first-line + last-line anchored fuzzy (middle lines must appear in order)
  S9 token-subsequence match (same word sequence, whitespace-insensitive,
     replaced as whole lines)

S8/S9 are last-resort; they only fire when the match is UNIQUE in the file
(the ambiguity check in fuzzy_replace applies to every strategy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_LINES_DEFAULT = 500
MAX_READ_CHARS = 100_000  # honest truncation cap (hermes read_file parity)


# ---------------------------------------------------------------- read_file
def render_lines(text: str, offset: int, limit: int) -> str:
    """Number lines 1-indexed, paginate, and truncate HONESTLY."""
    lines = text.splitlines()
    total = len(lines)
    start = max(1, offset)
    end = min(total, start + limit - 1)
    out: list[str] = []
    chars = 0
    cut_at = None
    for i in range(start - 1, end):
        line = f"{i + 1}|{lines[i]}"
        if chars + len(line) > MAX_READ_CHARS:
            cut_at = i + 1
            break
        out.append(line)
        chars += len(line) + 1
    result = "\n".join(out)
    if cut_at is not None:
        result += f"\n... [truncated at line {cut_at}; continue with offset={cut_at}]"
    elif end < total:
        result += f"\n... [showing {start}-{end} of {total}; next offset={end + 1}]"
    return result


# ---------------------------------------------------------------- edit ladder
@dataclass(frozen=True)
class _Match:
    start: int  # char offset in ORIGINAL text
    end: int


def _find_all(text: str, needle: str) -> list[_Match]:
    out: list[_Match] = []
    i = text.find(needle)
    while i >= 0:
        out.append(_Match(i, i + len(needle)))
        i = text.find(needle, i + len(needle))
    return out


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _regex_matches(text: str, pattern: str) -> list[_Match]:
    return [_Match(m.start(), m.end()) for m in re.finditer(pattern, text)]


def _s2(text: str, old: str) -> list[_Match]:
    """Trailing-whitespace tolerant: rstrip each old line, allow [ \\t]*
    before each newline."""
    parts = [re.escape(ln.rstrip()) for ln in old.split("\n")]
    return _regex_matches(text, "[ \t]*\n".join(parts) + "[ \t]*")


def _s3(text: str, old: str) -> list[_Match]:
    """Leading-indentation tolerant: lstrip each old line, allow [ \\t]*
    after each newline."""
    parts = [re.escape(ln.lstrip()) for ln in old.split("\n")]
    return _regex_matches(text, "\n[ \t]*".join(parts))


def _s4(text: str, old: str) -> list[_Match]:
    """Whitespace-collapsed: internal runs of spaces/tabs in old match any
    run in the file; also tolerates leading indent and trailing ws."""
    parts: list[str] = []
    for ln in old.split("\n"):
        toks = [re.escape(t) for t in ln.split() if t]
        parts.append("[ \t]+".join(toks))
    return _regex_matches(text, "[ \t]*\n[ \t]*".join(parts))


def _s5(text: str, old: str) -> list[_Match]:
    """Line-wise stripped: both ends of every line flexible."""
    parts = [re.escape(ln.strip()) for ln in old.split("\n")]
    return _regex_matches(text, "[ \t]*\n[ \t]*".join(parts))


def _s6(text: str, old: str) -> list[_Match]:
    """CRLF/LF normalized: only fires when the file contains CRLF."""
    if "\r\n" not in text:
        return []
    parts = [re.escape(ln.rstrip("\r")) for ln in old.split("\n")]
    return _regex_matches(text, "[ \t]*\r?\n".join(parts))


def _s7(text: str, old: str) -> list[_Match]:
    """Blank-line differences: extra or missing empty lines BETWEEN the
    matched (stripped) lines are tolerated."""
    parts = [re.escape(ln.strip()) for ln in old.split("\n") if ln.strip()]
    if len(parts) < 2:
        return []
    return _regex_matches(text, "[ \t]*\n(?:[ \t]*\n)*[ \t]*".join(parts))


def _s8(text: str, old: str) -> list[_Match]:
    """Anchored fuzzy: first and last non-blank lines must match exactly
    (stripped), and all middle lines must appear IN ORDER between them."""
    old_lines = [ln.strip() for ln in old.split("\n") if ln.strip()]
    if len(old_lines) < 3:
        return []
    starts = _line_starts(text)
    raw = text.split("\n")
    stripped = [ln.strip() for ln in raw]
    first, middle, last = old_lines[0], old_lines[1:-1], old_lines[-1]
    out: list[_Match] = []
    for i, ln in enumerate(stripped):
        if ln != first:
            continue
        # find last after i such that middle appears in order between
        pos = i + 1
        ok = True
        for m in middle:
            found = False
            while pos < len(stripped):
                if stripped[pos] == m:
                    found = True
                    pos += 1
                    break
                pos += 1
            if not found:
                ok = False
                break
        if not ok:
            continue
        for j in range(pos, len(stripped)):
            if stripped[j] == last:
                s = starts[i]
                e = starts[j + 1] - 1 if j + 1 < len(starts) else len(text)
                out.append(_Match(s, e))
                break
    return out


def _s9(text: str, old: str) -> list[_Match]:
    """Token-subsequence: same word sequence, any whitespace. Line-aligned
    spans: find the token window in the whole text, then expand to whole
    lines."""
    old_tokens = old.split()
    if not old_tokens:
        return []
    token_re = re.compile(r"\S+")
    toks = [(m.group(), m.start(), m.end()) for m in token_re.finditer(text)]
    n = len(old_tokens)
    out: list[_Match] = []
    i = 0
    while i <= len(toks) - n:
        if [t[0] for t in toks[i : i + n]] == old_tokens:
            s_tok = toks[i][1]
            e_tok = toks[i + n - 1][2]
            # expand to whole lines
            s = text.rfind("\n", 0, s_tok) + 1
            e = text.find("\n", e_tok)
            e = len(text) if e < 0 else e
            out.append(_Match(s, e))
            i += n
        else:
            i += 1
    return out


_LADDER: list[tuple[str, Any]] = [
    ("S1 exact", lambda t, o: _find_all(t, o)),
    ("S2 rstrip", _s2),
    ("S3 lstrip", _s3),
    ("S4 ws-collapsed", _s4),
    ("S5 stripped-lines", _s5),
    ("S6 crlf-normalized", _s6),
    ("S7 blank-lines", _s7),
    ("S8 anchored-fuzzy", _s8),
    ("S9 token-subsequence", _s9),
]


def fuzzy_replace(text: str, old: str, new: str, replace_all: bool = False) -> tuple[str, str]:
    """Apply the ladder. Returns (new_text, strategy_name).

    Raises ValueError with an honest message when nothing matches or the
    match is ambiguous — the caller converts it into an ERROR tool result so
    the model can retry with better context.
    """
    if not old:
        raise ValueError("old_string is empty")
    if old == new:
        raise ValueError("old_string and new_string are identical (no-op edit)")
    for name, fn in _LADDER:
        matches: list[_Match] = fn(text, old)
        if not matches:
            continue
        if len(matches) > 1 and not replace_all:
            raise ValueError(
                f"{name}: {len(matches)} matches — include more surrounding "
                "context to make it unique, or set replace_all=true"
            )
        out = text
        for m in reversed(matches if replace_all else matches[:1]):
            out = out[: m.start] + new + out[m.end :]
        return out, name
    raise ValueError("no strategy matched — old_string not found in file")


# ---------------------------------------------------------------- tools
def _resolve(workdir: Path, path_str: str) -> Path:
    """Resolve a user/model-supplied path against workdir.

    E3e PASO C: Windows paths (C:\\Users\\...) are normalized to their WSL
    mount (/mnt/c/Users/...) first. WinPathError propagates — callers turn
    it into an honest ERROR tool result.
    """
    from tlamati.tools.winpath import normalize_win_path

    p = Path(normalize_win_path(path_str)).expanduser()
    if not p.is_absolute():
        p = workdir / p
    return p.resolve()


def make_file_tools(workdir: Path) -> list[Any]:
    from tlamati.tools.registry import Permission, Tool
    from tlamati.tools.winpath import WinPathError

    async def read_file(args: dict[str, Any]) -> str:
        try:
            path = _resolve(workdir, str(args.get("path", "")))
        except WinPathError as e:
            return f"ERROR: {e}"
        if not path.is_file():
            return f"ERROR: no such file: {path}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"ERROR: {e}"
        offset = int(args.get("offset", 1))
        limit = int(args.get("limit", MAX_LINES_DEFAULT))
        return render_lines(text, offset, limit)

    async def write_file(args: dict[str, Any]) -> str:
        try:
            path = _resolve(workdir, str(args.get("path", "")))
        except WinPathError as e:
            return f"ERROR: {e}"
        content = str(args.get("content", ""))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"ERROR: {e}"
        return f"wrote {len(content)} chars to {path}"

    async def edit(args: dict[str, Any]) -> str:
        try:
            path = _resolve(workdir, str(args.get("path", "")))
        except WinPathError as e:
            return f"ERROR: {e}"
        if not path.is_file():
            return f"ERROR: no such file: {path}"
        old = str(args.get("old_string", ""))
        new = str(args.get("new_string", ""))
        replace_all = bool(args.get("replace_all", False))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"ERROR: {e}"
        try:
            out, strategy = fuzzy_replace(text, old, new, replace_all)
        except ValueError as e:
            return f"ERROR: edit failed — {e}"
        try:
            path.write_text(out, encoding="utf-8")
        except OSError as e:
            return f"ERROR: write failed — {e}"
        count = "all occurrences" if replace_all else "1 occurrence"
        return f"edited {path} ({count}, strategy {strategy})"

    return [
        Tool(
            name="read_file",
            description=(
                "Read a text file with numbered lines. Optional offset (1-indexed "
                f"start line) and limit (max lines, default {MAX_LINES_DEFAULT}). "
                "Large reads are truncated honestly with a next-offset hint."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "file path"},
                    "offset": {"type": "integer", "minimum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 2000},
                },
                "required": ["path"],
            },
            run=read_file,
            permission=Permission.AUTO,
        ),
        Tool(
            name="write_file",
            description=(
                "Write (create or FULLY overwrite) a text file. Parent dirs are "
                "created. For small changes to a big file prefer edit."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            run=write_file,
            permission=Permission.AUTO,
        ),
        Tool(
            name="edit",
            description=(
                "Targeted find-and-replace in a file (fuzzy matching: minor "
                "whitespace/indent differences tolerated). old_string must be "
                "UNIQUE unless replace_all=true; include surrounding context "
                "lines to disambiguate. new_string may be empty to delete."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean", "default": False},
                },
                "required": ["path", "old_string", "new_string"],
            },
            run=edit,
            permission=Permission.AUTO,
        ),
    ]
