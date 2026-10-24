"""Documentation checks: text hygiene, GitHub-flavoured markdown structure, links, privacy.

Every rule reports the number of objects it actually examined; a rule that examined
nothing is reported as `skipped`, never as `pass` (a green check that inspected zero
objects is a defect, not a success).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from .util import (
    FENCE_RE,
    IMAGE_RE,
    INLINE_LINK_RE,
    MARKDOWN_SUFFIXES,
    Report,
    iter_text_files,
    parse_table,
    prose_lines,
    read_text,
    rel,
    scan_structure,
)

ALLOWED_ALERTS = {"NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"}
TOC_TITLES = {"содержание", "оглавление", "contents", "table of contents", "toc", "навигация"}
SECRET_PATTERNS = [
    ("github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----")),
    ("slack-token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b")),
    ("bearer-literal", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b")),
]
ABS_PATH_PATTERNS = [
    re.compile(r"\b[A-Za-z]:[\\/]{1,2}(?:Users|Documents and Settings)[\\/]{1,2}[^\\/\s`'\"]+"),
    re.compile(r"(?<![\w.])/(?:home|Users)/[a-z0-9._-]+/", re.IGNORECASE),
]
PERSONAL_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
SAFE_EMAIL_DOMAINS = {
    "users.noreply.github.com", "example.com", "example.org", "example.net",
    "localhost", "deynekin.com",
}
KEBAB_TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class RuleStats:
    examined: int = 0
    skipped_reason: str = ""

    def touched(self) -> None:
        self.examined += 1


@dataclass
class DocCheckOptions:
    ignore: set[str] = field(default_factory=set)
    privacy: bool = True
    toc: bool = True
    line_length: int = 200
    max_line_rule: bool = True


class DocChecker:
    def __init__(self, root: Path, report: Report, options: DocCheckOptions | None = None) -> None:
        self.root = Path(root)
        self.report = report
        self.options = options or DocCheckOptions()
        self.stats: dict[str, RuleStats] = {}
        self.anchor_cache: dict[Path, set[str]] = {}

    # -- infrastructure ----------------------------------------------------
    def _rule(self, rule: str) -> bool:
        """Return True when the rule is active, and register it as examined."""
        stats = self.stats.setdefault(rule, RuleStats())
        if rule in self.options.ignore:
            stats.skipped_reason = "ignored by --ignore"
            return False
        return True

    def _hit(self, rule: str) -> None:
        self.stats.setdefault(rule, RuleStats()).touched()

    def anchors_of(self, path: Path) -> set[str]:
        resolved = path.resolve()
        if resolved not in self.anchor_cache:
            try:
                text, _ = read_text(path)
            except (OSError, ValueError):
                self.anchor_cache[resolved] = set()
            else:
                headings, _, _, _ = scan_structure(text)
                self.anchor_cache[resolved] = {h.anchor for h in headings}
        return self.anchor_cache[resolved]

    # -- entry point -------------------------------------------------------
    def check_tree(self, *, suffixes: set[str] | None = None) -> None:
        files = list(iter_text_files(self.root, suffix_set=suffixes))
        if not files:
            self.report.error("doc.no-text-files", f"no text files found under {self.root}; nothing was examined")
            return
        for path in files:
            self.check_file(path)
        self._report_coverage()

    def check_file(self, path: Path) -> None:
        relative = rel(path, self.root)
        try:
            text, meta = read_text(path)
        except ValueError as exc:
            if self._rule("doc.utf8"):
                self._hit("doc.utf8")
                self.report.error("doc.utf8", str(exc), path=relative,
                                  hint="re-save the file as UTF-8 (no conversion table)")
            return
        except OSError as exc:
            self.report.error("doc.unreadable", str(exc), path=relative)
            return

        if self._rule("doc.bom"):
            self._hit("doc.bom")
            if meta.has_bom:
                self.report.error("doc.bom", "file starts with a UTF-8 BOM", path=relative, line=1,
                                  hint="save as UTF-8 without BOM")
        if self._rule("doc.crlf"):
            self._hit("doc.crlf")
            if meta.has_crlf:
                self.report.error("doc.crlf", f"{meta.crlf_count} CRLF line ending(s)",
                                  path=relative, line=1, hint="normalise to LF")
        if self._rule("doc.final-newline"):
            self._hit("doc.final-newline")
            if not meta.ends_with_newline and meta.size:
                self.report.warn("doc.final-newline", "file does not end with a newline", path=relative)
        if self._rule("doc.tab-indent"):
            self._hit("doc.tab-indent")
            if meta.has_tab_indent:
                self.report.warn("doc.tab-indent", "tab-indented block", path=relative,
                                 hint="use spaces (4) or a fence")

        if path.suffix.lower() in MARKDOWN_SUFFIXES:
            self.check_markdown(path, text, relative)
        if self.options.privacy:
            self.check_privacy(relative, text)

    # -- markdown ----------------------------------------------------------
    def check_markdown(self, path: Path, text: str, relative: str) -> None:
        headings, fences, links, lines = scan_structure(text)
        # A template carries unresolved placeholders on purpose: `<owner>`, `(<path>)`.
        # The marker is explicit so that a normal document cannot opt out by accident.
        is_template = "<!-- ghagent: template -->" in text
        if is_template:
            self.report.data.setdefault("templates", []).append(relative)

        if self._rule("md.h1"):
            self._hit("md.h1")
            h1 = [h for h in headings if h.level == 1]
            is_template = ".github" in path.parts or "template" in path.name.lower()
            is_template = is_template or "<!-- ghagent: template -->" in text
            if not h1:
                if is_template:
                    self.report.info("md.h1", "template without an H1 (expected: the body starts at H2)",
                                     path=relative, line=1)
                else:
                    self.report.error("md.h1", "no H1 heading", path=relative, line=1,
                                      hint="a document needs exactly one H1")
            elif len(h1) > 1:
                extra = ", ".join(str(h.line) for h in h1[1:])
                self.report.error("md.h1", f"{len(h1)} H1 headings (extra at line {extra})",
                                  path=relative, line=h1[1].line, hint="keep one H1, demote the rest")

        if self._rule("md.heading-skip"):
            self._hit("md.heading-skip")
            previous = 0
            for heading in headings:
                if previous and heading.level - previous > 1:
                    self.report.warn("md.heading-skip",
                                     f"H{previous} -> H{heading.level} skips a level",
                                     path=relative, line=heading.line)
                previous = heading.level

        if self._rule("md.fence"):
            for fence in fences:
                self._hit("md.fence")
                if fence.closed_at is None:
                    self.report.error("md.fence", f"unclosed {fence.marker} fence",
                                      path=relative, line=fence.line, hint="close the code block")
                elif not fence.info:
                    self.report.warn("md.fence", "code fence without a language tag",
                                     path=relative, line=fence.line,
                                     hint="add the language (`bash`, `json`, `text`)")

        self._check_tables(lines, relative)

        structural_links = not is_template

        if self._rule("md.image-alt"):
            for link in links:
                if link.is_image:
                    self._hit("md.image-alt")
                    if not link.text.strip():
                        self.report.warn("md.image-alt", f"image without alt text: {link.target}",
                                         path=relative, line=link.line)

        self._check_alerts(lines, relative)

        if self.options.max_line_rule and self._rule("doc.line-length"):
            for number, raw in prose_lines(text):
                self._hit("doc.line-length")
                stripped = raw.strip()
                if len(raw) > self.options.line_length and not stripped.startswith("|") and "http" not in stripped:
                    self.report.info("doc.line-length",
                                     f"prose line is {len(raw)} characters",
                                     path=relative, line=number,
                                     hint=f"wrap around {self.options.line_length - 40}")
                if raw.rstrip("\n").endswith("  ") and raw.strip():
                    stripped_no_break = raw.rstrip()
                    if stripped_no_break.endswith("  "):
                        self.report.warn("md.hard-break", "trailing double space (markdown hard break)",
                                         path=relative, line=number, hint="use a blank line instead")

        self._check_links(path, relative, links, headings, text) if structural_links else None
        if self.options.toc and structural_links:
            self._check_toc(relative, headings, lines)

    def _check_tables(self, lines: list[str], relative: str) -> None:
        if not self._rule("md.table"):
            return
        index = 0
        while index < len(lines):
            if "|" in lines[index] and index + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[index + 1]) and "-" in lines[index + 1]:
                table = parse_table(lines, index)
                if table:
                    self._hit("md.table")
                    if table["header_cells"] != table["align_cells"]:
                        self.report.error("md.table",
                                          f"header has {table['header_cells']} cell(s), separator has {table['align_cells']}",
                                          path=relative, line=table["start_line"] + 1)
                    for offset, row in enumerate(table["rows"]):
                        if len(row) != table["header_cells"]:
                            self.report.error("md.table",
                                              f"row has {len(row)} cell(s), header has {table['header_cells']}",
                                              path=relative, line=table["start_line"] + 2 + offset)
                    index = table["end_line"]
                    continue
            index += 1

    def _check_alerts(self, lines: list[str], relative: str) -> None:
        if not self._rule("md.alert"):
            return
        for number, raw in enumerate(lines, start=1):
            match = re.match(r"^\s*>\s*\[!([A-Za-z]+)\]", raw)
            if not match:
                continue
            self._hit("md.alert")
            if match.group(1).upper() not in ALLOWED_ALERTS:
                self.report.warn("md.alert", f"unknown alert type [!{match.group(1)}]",
                                 path=relative, line=number,
                                 hint="allowed: " + ", ".join(sorted(ALLOWED_ALERTS)))

    def _check_links(self, path: Path, relative: str, links, headings, text: str) -> None:
        local_anchors = {h.anchor for h in headings}
        for link in links:
            if link.kind != "inline":
                continue
            target = link.target.strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "ftp://")):
                continue
            if any(token in target for token in ("<", ">", "{{", "}}", "${")):
                continue  # placeholder kept on purpose in templates
            if self._rule("md.link-local"):
                self._hit("md.link-local")
                self._resolve_link(path, relative, link, local_anchors)

    def _resolve_link(self, path: Path, relative: str, link, local_anchors: set[str]) -> None:
        target = link.target.strip()
        anchorless = target.split("#", 1)[0]
        anchor = target.split("#", 1)[1] if "#" in target else ""
        if anchorless:
            candidate = (path.parent / unquote(anchorless)).resolve()
            if candidate.is_dir():
                self.report.warn("md.link-dir", f"link points to a directory: {target}",
                                 path=relative, line=link.line)
                return
            if not candidate.exists():
                self.report.error("md.link-local", f"target does not exist: {target}",
                                  path=relative, line=link.line,
                                  hint="fix the path or drop the link")
                return
            if anchor and candidate.suffix.lower() in MARKDOWN_SUFFIXES:
                if anchor.lower() not in {a.lower() for a in self.anchors_of(candidate)}:
                    self.report.error("md.link-anchor",
                                      f"anchor #{anchor} not found in {anchorless}",
                                      path=relative, line=link.line)
            return
        if anchor:
            normalised = anchor.lower()
            if normalised.startswith("user-content-"):
                normalised = normalised[len("user-content-"):]
            if normalised not in {a.lower() for a in local_anchors}:
                self.report.error("md.link-anchor", f"anchor #{anchor} not found in this document",
                                  path=relative, line=link.line,
                                  hint="heading anchors are lowercased, punctuation dropped, spaces to hyphens")

    def _check_toc(self, relative: str, headings, lines: list[str]) -> None:
        if not self._rule("md.toc"):
            return
        toc_start = None
        for heading in headings:
            if heading.text.strip().lower().strip(":") in TOC_TITLES:
                toc_start = heading
                break
        if toc_start is None:
            return
        self._hit("md.toc")
        listed: set[str] = set()
        start_index = toc_start.line  # 0-based index of the line after the heading
        for raw in lines[start_index:]:
            if re.match(r"^#{1,6}\s", raw):
                break
            for match in INLINE_LINK_RE.finditer(raw):
                target = match.group(2)
                if target.startswith("#"):
                    listed.add(target[1:].lower())
        known = {h.anchor.lower() for h in headings if h.anchor}
        for anchor in sorted(listed - known):
            self.report.error("md.toc", f"table of contents lists #{anchor}, which no heading produces",
                              path=relative, line=toc_start.line)
        missing = [h for h in headings
                   if h.level == 2
                   and h is not toc_start
                   and h.anchor.lower() not in listed]
        if missing:
            sample = ", ".join(f"H2 '{h.text[:40]}'" for h in missing[:5])
            self.report.warn("md.toc", f"{len(missing)} H2 section(s) missing from the table of contents: {sample}",
                             path=relative, line=toc_start.line)

    # -- privacy -----------------------------------------------------------
    def check_privacy(self, relative: str, text: str) -> None:
        if self._rule("privacy.secret"):
            for name, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    self._hit("privacy.secret")
                    line = text.count("\n", 0, match.start()) + 1
                    self.report.error("privacy.secret", f"{name} literal in file",
                                      path=relative, line=line,
                                      hint="remove the value; reference an environment variable by name")
        if self._rule("privacy.abs-path"):
            for pattern in ABS_PATH_PATTERNS:
                for match in pattern.finditer(text):
                    self._hit("privacy.abs-path")
                    line = text.count("\n", 0, match.start()) + 1
                    self.report.error("privacy.abs-path",
                                      "absolute machine path in a published file",
                                      path=relative, line=line,
                                      hint="use a relative path or a <placeholder>")
        if self._rule("privacy.email"):
            for match in PERSONAL_EMAIL_RE.finditer(text):
                domain = match.group(1).lower()
                if domain in SAFE_EMAIL_DOMAINS:
                    continue
                self._hit("privacy.email")
                line = text.count("\n", 0, match.start()) + 1
                self.report.warn("privacy.email",
                                 f"personal e-mail address ({domain})",
                                 path=relative, line=line,
                                 hint="use a role address or a noreply address")

    # -- coverage ----------------------------------------------------------
    def _report_coverage(self) -> None:
        skipped = {rule: s for rule, s in self.stats.items() if s.examined == 0 and s.skipped_reason}
        untouched = {rule: s for rule, s in self.stats.items() if s.examined == 0 and not s.skipped_reason}
        for rule in sorted(untouched):
            self.report.info("coverage.skipped", f"rule {rule} examined nothing on this tree")
        self.report.data["rules_examined"] = {rule: s.examined for rule, s in sorted(self.stats.items())}
        self.report.data["rules_ignored"] = sorted(skipped)


def check_paths(root: Path, targets: list[Path], options: DocCheckOptions | None = None) -> Report:
    report = Report(title="ghagent doc", root=str(root))
    checker = DocChecker(root, report, options)
    for path in targets:
        if path.suffix.lower() in MARKDOWN_SUFFIXES or path.suffix.lower() in {".txt", ".yml", ".yaml", ".json", ".cff", ".ps1", ".py", ".sh"}:
            checker.check_file(path)
        else:
            checker.check_file(path)
    checker._report_coverage()
    return report
