"""Shared primitives for ghalib: text hygiene, GitHub anchors, markdown parsing, findings.

Standard library only. Every helper here is exercised by tests/run_tests.py.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

PACK_NAME = "github-agent"
PACK_VERSION = "1.2.0"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

# Directories that are never part of a repository's own documentation surface.
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".ragraf", ".zwork", ".agents", ".dev_agent", ".pi",
    "node_modules", "vendor", "bower_components", ".venv", "venv", "env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "target", "coverage", "htmlcov", ".tox", ".idea", ".vscode",
}

TEXT_SUFFIXES = {
    ".md", ".markdown", ".mdown", ".txt", ".rst", ".yml", ".yaml", ".json",
    ".toml", ".ini", ".cfg", ".cff", ".py", ".ps1", ".psm1", ".sh", ".bash",
    ".js", ".mjs", ".ts", ".php", ".css", ".html", ".xml", ".sql", ".bat", ".cmd",
}

MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown"}


# --------------------------------------------------------------------------
# text input / output
# --------------------------------------------------------------------------

@dataclass
class TextMeta:
    path: Path
    has_bom: bool
    crlf_count: int
    lf_count: int
    has_tab_indent: bool
    ends_with_newline: bool
    size: int

    @property
    def has_crlf(self) -> bool:
        return self.crlf_count > 0

    @property
    def mixed_eol(self) -> bool:
        return self.crlf_count > 0 and self.lf_count > 0


def read_text(path: Path) -> tuple[str, TextMeta]:
    raw = Path(path).read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    if has_bom:
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:  # invalid UTF-8 is a finding, not a crash
        raise ValueError(f"{path}: not valid UTF-8 ({exc.reason} at byte {exc.start})") from exc
    meta = TextMeta(
        path=Path(path),
        has_bom=has_bom,
        crlf_count=text.count("\r\n"),
        lf_count=text.count("\n") - text.count("\r\n"),
        has_tab_indent=bool(re.search(r"^\t+", text, re.MULTILINE)),
        ends_with_newline=text.endswith("\n"),
        size=len(raw),
    )
    return text.replace("\r\n", "\n").replace("\r", "\n"), meta


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 without BOM and with LF endings, atomically."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".ghagent-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def force_utf8_stdio() -> None:
    """Write stdout and stderr as UTF-8 even when they are redirected.

    On Windows a redirected stream is encoded with the locale codec (cp1252, cp866,
    cp1251), which cannot carry the arrows, ellipses and non-Latin scripts the reports
    are made of: the command would die with UnicodeEncodeError instead of printing its
    finding. PEP 528 already gives the console UTF-8, so only the redirected case needs
    this. `backslashreplace` keeps the exit code and the rest of the report intact if a
    stream still refuses a character. Every failure is swallowed on purpose: a stream
    that cannot be reconfigured (bytes, a test harness, an already wrapped console) must
    never turn a usable run into a crash.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass


def iter_text_files(root: Path, *, suffix_set: set[str] | None = None):
    root = Path(root)
    suffixes = suffix_set if suffix_set is not None else TEXT_SUFFIXES
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".ghagent-"))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() in suffixes:
                yield path


def rel(path: Path, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


# --------------------------------------------------------------------------
# GitHub heading anchors
# --------------------------------------------------------------------------

def strip_inline_markdown(text: str) -> str:
    """Reduce inline markdown to the text GitHub renders, for anchor computation."""
    out = text
    out = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", out)          # images -> alt
    out = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", out)           # links -> text
    out = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", out)          # reference links
    out = re.sub(r"`([^`]*)`", r"\1", out)                       # inline code keeps text
    out = re.sub(r"<[^>]+>", "", out)                            # html tags
    out = re.sub(r"(\*\*|__)(.*?)\1", r"\2", out)                # bold
    out = re.sub(r"(\*|_)(.*?)\1", r"\2", out)                   # italic
    out = re.sub(r"~~(.*?)~~", r"\1", out)                       # strike
    return out.strip()


def _anchor_keep(ch: str) -> bool:
    """Letters, digits and combining marks survive; punctuation is dropped.

    All three mark categories are kept, not only `Mn`: Devanagari vowel signs are
    spacing combining marks (`Mc`), and dropping them turns `इंस्टॉलेशन` into
    `इंस्टलेशन`, so a table-of-contents link to the heading stops resolving. GitHub
    keeps the mark, so the anchor keeps it too.
    """
    if ch in "-_ ":
        return True
    category = unicodedata.category(ch)
    return category[0] in {"L", "N", "M"}


def slugify(heading: str) -> str:
    """Reproduce GitHub's heading anchor: lowercase, drop punctuation, spaces to hyphens.

    Letters, digits and combining marks survive, so scripts that write a vowel as a
    separate mark (Devanagari, Thai, Vietnamese) keep it exactly as GitHub renders it.
    Verified against a live repo TOC (em dash removal leaves a double hyphen).
    """
    text = strip_inline_markdown(heading).lower()
    kept = "".join(ch for ch in text if _anchor_keep(ch))
    return kept.replace(" ", "-")


class SlugRegistry:
    """Anchors are unique per document; duplicates get -1, -2 suffixes like GitHub."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def add(self, heading: str) -> str:
        base = slugify(heading)
        if base not in self._seen:
            self._seen[base] = 1
            return base
        count = self._seen[base]
        self._seen[base] = count + 1
        candidate = f"{base}-{count}"
        while candidate in self._seen:
            count += 1
            self._seen[base] = count
            candidate = f"{base}-{count}"
        self._seen[candidate] = 1
        return candidate


# --------------------------------------------------------------------------
# markdown structure
# --------------------------------------------------------------------------

@dataclass
class Heading:
    level: int
    text: str
    line: int
    anchor: str = ""


@dataclass
class Link:
    text: str
    target: str
    line: int
    is_image: bool = False
    kind: str = "inline"   # inline | reference | autolink


@dataclass
class Fence:
    line: int
    marker: str
    info: str
    closed_at: int | None = None


FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})(?P<space>[ \t]+)(?P<text>.*?)(?:[ \t]+#+)?[ \t]*$")
INLINE_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")
AUTOLINK_RE = re.compile(r"<((?:https?|ftp)://[^>\s]+)>")
BARE_URL_RE = re.compile(r"(?<![(<\[`\"'])\bhttps?://[^\s`<>)\]]+")


def scrub_code_spans(line: str) -> str:
    """Blank out inline code so that a link written inside backticks is not treated as a link."""
    return re.sub(r"``[^`]*``|`[^`]*`", " ", line)


CODE_SPAN_SPLIT = re.compile(r"(``[^`]*``|`[^`]*`)")


def map_outside_code(line: str, transform) -> str:
    """Apply `transform` to the parts of a line that are not inside inline code."""
    parts = CODE_SPAN_SPLIT.split(line)
    for index, part in enumerate(parts):
        if index % 2 == 1:      # odd indexes are the code spans themselves
            continue
        parts[index] = transform(part)
    return "".join(parts)


def scan_structure(text: str) -> tuple[list[Heading], list[Fence], list[Link], list[str]]:
    """Return headings (with anchors), fences, links and the raw lines."""
    lines = text.split("\n")
    headings: list[Heading] = []
    fences: list[Fence] = []
    links: list[Link] = []
    registry = SlugRegistry()
    in_fence: Fence | None = None

    for number, raw in enumerate(lines, start=1):
        match = FENCE_RE.match(raw)
        if in_fence is None:
            if match:
                fence = Fence(line=number, marker=match.group("marker"), info=match.group("info").strip())
                fences.append(fence)
                in_fence = fence
                continue
            heading_match = HEADING_RE.match(raw)
            if heading_match:
                heading_text = heading_match.group("text").strip()
                headings.append(Heading(
                    level=len(heading_match.group("hashes")),
                    text=heading_text,
                    line=number,
                    anchor=registry.add(heading_text),
                ))
            # Links inside inline code are literal text, not links.
            for image in IMAGE_RE.finditer(scrub_code_spans(raw)):
                links.append(Link(text=image.group(1), target=image.group(2), line=number, is_image=True))
            scrubbed = scrub_code_spans(raw)
            for link in INLINE_LINK_RE.finditer(scrubbed):
                links.append(Link(text=link.group(1), target=link.group(2), line=number))
            for ref in REF_LINK_RE.finditer(scrubbed):
                links.append(Link(text=ref.group(1), target=ref.group(2), line=number, kind="reference"))
            for auto in AUTOLINK_RE.finditer(scrubbed):
                links.append(Link(text=auto.group(1), target=auto.group(1), line=number, kind="autolink"))
        else:
            if match and match.group("marker")[0] == in_fence.marker[0] and len(match.group("marker")) >= len(in_fence.marker):
                in_fence.closed_at = number
                in_fence = None

    return headings, fences, links, lines


def parse_table(lines: list[str], start_index: int) -> dict | None:
    """Parse a pipe table starting at lines[start_index]; returns counts and rows."""
    header = lines[start_index]
    if start_index + 1 >= len(lines):
        return None
    separator = lines[start_index + 1]
    if not re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", separator) or "-" not in separator:
        return None
    header_cells = split_row(header)
    align_cells = split_row(separator)
    rows: list[list[str]] = []
    index = start_index + 2
    while index < len(lines) and lines[index].strip() and "|" in lines[index]:
        rows.append(split_row(lines[index]))
        index += 1
    return {
        "start_line": start_index + 1,
        "header_cells": len(header_cells),
        "align_cells": len(align_cells),
        "rows": rows,
        "end_line": index,
    }


def split_row(row: str) -> list[str]:
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    index = 0
    while index < len(stripped):
        ch = stripped[index]
        if ch == "\\" and index + 1 < len(stripped) and stripped[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(ch)
        index += 1
    cells.append("".join(current).strip())
    return cells


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Lines outside fenced code blocks, with their 1-based numbers."""
    result: list[tuple[int, str]] = []
    in_fence = False
    for number, raw in enumerate(text.split("\n"), start=1):
        match = FENCE_RE.match(raw)
        if match:
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((number, raw))
    return result


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------

@dataclass
class Finding:
    level: str            # error | warn | info
    rule: str
    message: str
    path: str = ""
    line: int = 0
    hint: str = ""

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "rule": self.rule,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "hint": self.hint,
        }

    def render(self) -> str:
        location = self.path or "-"
        if self.line:
            location = f"{location}:{self.line}"
        tail = f"  hint: {self.hint}" if self.hint else ""
        return f"[{self.level.upper():5}] {self.rule:22} {location}  {self.message}{tail}"


@dataclass
class Report:
    title: str
    root: str = ""
    findings: list[Finding] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def add(self, level: str, rule: str, message: str, *, path: str = "", line: int = 0, hint: str = "") -> None:
        self.findings.append(Finding(level=level, rule=rule, message=message, path=path, line=line, hint=hint))

    def error(self, rule: str, message: str, **kw) -> None:
        self.add("error", rule, message, **kw)

    def warn(self, rule: str, message: str, **kw) -> None:
        self.add("warn", rule, message, **kw)

    def info(self, rule: str, message: str, **kw) -> None:
        self.add("info", rule, message, **kw)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warn"]

    def counts(self) -> dict:
        return {
            "error": len(self.errors),
            "warn": len(self.warnings),
            "info": len([f for f in self.findings if f.level == "info"]),
        }

    def exit_code(self) -> int:
        return EXIT_FAIL if self.errors else EXIT_OK

    def render(self) -> str:
        lines = [self.title]
        if self.root:
            lines.append(f"root: {self.root}")
        for finding in sorted(self.findings, key=lambda f: ({"error": 0, "warn": 1, "info": 2}[f.level], f.path, f.line)):
            lines.append(finding.render())
        counts = self.counts()
        verdict = "FAIL" if counts["error"] else ("WARN" if counts["warn"] else "PASS")
        lines.append(f"{verdict}: {counts['error']} error(s), {counts['warn']} warning(s), {counts['info']} note(s)")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "root": self.root,
            "counts": self.counts(),
            "findings": [f.as_dict() for f in self.findings],
            "data": self.data,
        }


def emit(report: Report, as_json: bool) -> int:
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.render())
    return report.exit_code()


# --------------------------------------------------------------------------
# process helpers
# --------------------------------------------------------------------------

def which(program: str) -> str | None:
    return shutil.which(program)


def run(cmd: list[str], cwd: Path | None = None, *, check: bool = False) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.returncode, proc.stdout, proc.stderr


def git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    return run(["git", *args], cwd=cwd)


def repo_root_from(path: Path) -> Path:
    rc, out, _ = git(["rev-parse", "--show-toplevel"], path)
    if rc == 0 and out.strip():
        return Path(out.strip())
    return path


def guess_repo_slug(path: Path) -> tuple[str, str] | None:
    """Read owner/repo from the `origin` remote, if any."""
    rc, out, _ = git(["remote", "get-url", "origin"], path)
    if rc != 0:
        return None
    url = out.strip()
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    if not match:
        return None
    return match.group(1), match.group(2)


def fail(message: str) -> int:
    print(f"ghagent: {message}", file=sys.stderr)
    return EXIT_USAGE
