"""CHANGELOG.md work: conformance check, releasing Unreleased, generating entries.

The contract this module enforces is Keep a Changelog 1.1.0 plus semantic versioning:

    # Changelog
    All notable changes are documented here. Format: Keep a Changelog 1.1.0, SemVer 2.0.0.
    ## [Unreleased]
    ## [1.2.3] - 2026-10-24
    ### Added
    - Something a user can see.
    ...
    [Unreleased]: https://github.com/<owner>/<repo>/compare/v1.2.3...HEAD
    [1.2.3]: https://github.com/<owner>/<repo>/compare/v1.2.2...v1.2.3

Two rules are not obvious and are easy to get wrong:
  * a version section without a date cannot be linked or sorted, so it is an error;
  * 'Unreleased' is the only heading that is allowed to have no date.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from .util import Report, read_text, run, scan_structure, write_text

TYPES_EN = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
TYPES_RU = ["Добавлено", "Изменено", "Устарело", "Удалено", "Исправлено", "Безопасность"]
TYPE_ALIASES = {name.lower(): name for name in TYPES_EN}
TYPE_ALIASES.update({name.lower(): name for name in TYPES_RU})

VERSION_RE = re.compile(
    r"^\[?(?P<version>\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?(?:\+[0-9A-Za-z.\-]+)?)\]?"
    r"(?:\s*[-—–]\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
LINK_REF_RE = re.compile(r"^\[(?P<label>[^\]]+)\]:\s*(?P<url>\S+)\s*$")
CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s*(?P<description>.+)$"
)
TYPE_TO_SECTION = {
    "feat": "Added",
    "feature": "Added",
    "fix": "Fixed",
    "bugfix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "docs": "Changed",
    "style": "Changed",
    "revert": "Removed",
    "remove": "Removed",
    "security": "Security",
    "deprecate": "Deprecated",
    "build": "Changed",
}
NOISE_TYPES = {"chore", "test", "tests", "ci", "wip", "release"}
SECTION_ORDER = {name.lower(): index for index, name in enumerate(TYPES_EN)}
SECTION_ORDER.update({name.lower(): index for index, name in enumerate(TYPES_RU)})


@dataclass
class VersionSection:
    version: str
    date: str
    line: int
    sections: list[tuple[str, int]]     # (heading text, line)
    items: int = 0


def section_name(heading: str) -> str | None:
    return TYPE_ALIASES.get(heading.strip().lower())


def parse(text: str) -> tuple[list[VersionSection], dict[str, str]]:
    headings, _, _, lines = scan_structure(text)
    versions: list[VersionSection] = []
    references: dict[str, str] = {}
    for raw in lines:
        match = LINK_REF_RE.match(raw.strip())
        if match:
            references[match.group("label").lower()] = match.group("url")

    current: VersionSection | None = None
    current_section_start: int | None = None
    for index, raw in enumerate(lines, start=1):
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            if level == 2:
                if current and current_section_start is not None:
                    current.items += _count_items(lines, current_section_start, index)
                current_section_start = None
                if title.strip().strip("[]").lower() in {"unreleased", "не выпущено", "невыпущено"}:
                    current = VersionSection(version="Unreleased", date="", line=index, sections=[])
                    versions.append(current)
                    continue
                match = VERSION_RE.match(title)
                if match:
                    current = VersionSection(version=match.group("version"),
                                             date=match.group("date") or "", line=index, sections=[])
                    versions.append(current)
                else:
                    current = None
                continue
            if level == 3 and current is not None:
                current.sections.append((title, index))
                current_section_start = index
    if current and current_section_start is not None:
        current.items += _count_items(lines, current_section_start, len(lines) + 1)
    return versions, references


def _count_items(lines: list[str], start: int, end: int) -> int:
    count = 0
    for raw in lines[start:end - 1]:
        if re.match(r"^\s*[-*]\s+\S", raw):
            count += 1
    return count


def _semver_key(version: str) -> tuple:
    core = version.split("-", 1)[0].split("+", 1)[0]
    parts = [int(p) for p in core.split(".")]
    while len(parts) < 3:
        parts.append(0)
    pre = version.split("-", 1)[1].split("+", 1)[0] if "-" in version else ""
    return (parts[0], parts[1], parts[2], 0 if pre else 1, pre)


def check(path: Path, *, report: Report | None = None, slug: str = "", today: dt.date | None = None) -> Report:
    path = Path(path)
    report = report or Report(title="ghagent changelog check", root=str(path.parent))
    if not path.exists():
        report.error("changelog.missing", f"{path.name} is absent")
        return report
    text, meta = read_text(path)
    if meta.has_bom:
        report.error("doc.bom", "CHANGELOG starts with a BOM", path=path.name)
    if meta.has_crlf:
        report.error("doc.crlf", "CHANGELOG uses CRLF", path=path.name)

    headings, _, _, lines = scan_structure(text)
    h1 = [h for h in headings if h.level == 1]
    if not h1:
        report.error("changelog.h1", "no H1 heading", path=path.name)
    elif len(h1) > 1:
        report.error("changelog.h1", f"{len(h1)} H1 headings", path=path.name)
    if h1 and h1[0].line != 1:
        report.warn("changelog.h1-position", f"H1 is on line {h1[0].line}, not line 1", path=path.name)

    preamble_lines: list[str] = []
    for raw in lines:
        if re.match(r"^##\s", raw):
            break
        preamble_lines.append(raw)
    preamble = "\n".join(preamble_lines).lower()
    if "keep a changelog" not in preamble:
        report.warn("changelog.format-link", "the preamble does not mention Keep a Changelog",
                    path=path.name, hint="state the format and link it")
    if "semantic versioning" not in preamble and "semver" not in preamble:
        report.warn("changelog.semver-link", "the preamble does not mention Semantic Versioning", path=path.name)

    versions, references = parse(text)
    released = [v for v in versions if v.version != "Unreleased"]
    today = today or dt.date.today()

    if not versions:
        report.error("changelog.versions", "no version sections found", path=path.name)
        return report
    if not any(v.version == "Unreleased" for v in versions):
        report.warn("changelog.unreleased", "no [Unreleased] section", path=path.name,
                    hint="pending work becomes invisible without it")
    if versions[0].version != "Unreleased" and released and versions[0] is not released[0]:
        pass

    seen: dict[str, int] = {}
    previous_key: tuple | None = None
    previous_date: str | None = None
    for section in released:
        if section.version in seen:
            report.error("changelog.duplicate", f"version {section.version} appears twice",
                         path=path.name, line=section.line)
        seen[section.version] = section.line
        if not section.date:
            report.error("changelog.date-missing", f"version {section.version} has no ISO date",
                         path=path.name, line=section.line, hint="## [x.y.z] - YYYY-MM-DD")
        else:
            try:
                parsed_date = dt.date.fromisoformat(section.date)
            except ValueError:
                report.error("changelog.date-format", f"version {section.version} has a non-ISO date '{section.date}'",
                             path=path.name, line=section.line)
            else:
                if parsed_date > today:
                    report.warn("changelog.date-future", f"version {section.version} is dated in the future",
                                path=path.name, line=section.line)
                if previous_date and section.date > previous_date:
                    report.error("changelog.order", f"version {section.version} is dated after the entry above it",
                                 path=path.name, line=section.line, hint="the latest version comes first")
                previous_date = section.date or previous_date
        key = _semver_key(section.version)
        if previous_key and key > previous_key:
            report.error("changelog.order", f"version {section.version} is greater than the version listed above it",
                         path=path.name, line=section.line, hint="sort newest first")
        previous_key = key

        if not section.sections:
            report.error("changelog.empty-version", f"version {section.version} has no change subsections",
                         path=path.name, line=section.line)
        if section.sections and section.items == 0:
            report.error("changelog.empty-version", f"version {section.version} has headings but no entries",
                         path=path.name, line=section.line)

        names: list[str] = []
        for heading, line in section.sections:
            canonical = section_name(heading)
            if canonical is None:
                report.warn("changelog.types", f"unknown change type '{heading}'",
                            path=path.name, line=line, hint="allowed: " + ", ".join(TYPES_EN))
                continue
            names.append(canonical)
        indexes = [SECTION_ORDER.get(name.lower(), 99) for name in names]
        if indexes != sorted(indexes):
            report.warn("changelog.type-order", f"version {section.version}: sections are out of the canonical order",
                        path=path.name, line=section.line, hint="order: " + ", ".join(TYPES_EN))

    uses_brackets = any(re.match(r"^##\s+\[", raw) for raw in lines)
    if uses_brackets:
        if not references:
            report.error("changelog.link-refs", "versions use [x.y.z] but there are no link references at the bottom",
                         path=path.name, hint="add `[x.y.z]: https://…/compare/…` lines")
        else:
            for label in ["unreleased", *[v.version.lower() for v in released]]:
                if label not in references:
                    report.warn("changelog.link-refs", f"no link reference for [{label}]", path=path.name)
    if slug and references:
        wrong = [value for value in references.values() if "github.com" in value and slug not in value]
        if wrong:
            report.warn("changelog.link-refs", "a link reference points at another repository",
                        path=path.name, hint=f"expected links under github.com/{slug}")

    report.data.update({
        "versions": len(released),
        "unreleased_items": next((v.items for v in versions if v.version == "Unreleased"), 0),
        "latest": released[0].version if released else "",
        "links": len(references),
    })
    return report


# --------------------------------------------------------------------------
# release: promote Unreleased
# --------------------------------------------------------------------------

def release(path: Path, version: str, *, date: str = "", write: bool = False, slug: str = "",
            report: Report | None = None) -> Report:
    path = Path(path)
    report = report or Report(title=f"ghagent changelog release {version}", root=str(path.parent))
    if not version or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?", version):
        report.error("changelog.version", f"'{version}' is not a semantic version")
        return report
    if not path.exists():
        report.error("changelog.missing", f"{path.name} is absent")
        return report

    text, _ = read_text(path)
    versions, references = parse(text)
    released = [v for v in versions if v.version != "Unreleased"]
    if any(v.version == version for v in released):
        report.error("changelog.duplicate", f"version {version} already exists", path=path.name)
        return report
    unreleased = next((v for v in versions if v.version == "Unreleased"), None)
    if unreleased is None:
        report.error("changelog.unreleased", "no [Unreleased] section to promote", path=path.name)
        return report
    if not unreleased.sections:
        report.error("changelog.empty-version", "[Unreleased] has no change subsections", path=path.name)
        return report
    date = date or dt.date.today().isoformat()
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        report.error("changelog.date-format", f"'{date}' is not an ISO date")
        return report

    lines = text.split("\n")
    start = unreleased.line            # 1-based heading line
    end = len(lines)
    for later in versions[versions.index(unreleased) + 1:]:
        end = later.line - 1
        break
    body = lines[start:end]
    while body and not body[-1].strip():
        body.pop()

    new_block = [f"## [{version}] - {date}"] + body[1:]
    result_lines = lines[: start - 1] + ["## [Unreleased]", ""] + new_block + [""] + lines[end:]
    new_text = "\n".join(result_lines)
    new_text = _update_references(new_text, version, slug or _slug_from_references(references))

    report.data.update({
        "version": version,
        "date": date,
        "entries": unreleased.items,
        "written": False,
    })
    if not write:
        report.info("changelog.dry-run", f"would promote [Unreleased] ({unreleased.items} entries) to [{version}] - {date}",
                    hint="pass --write to apply")
        return report

    if not any(v.version == version for v in parse(new_text)[0]):
        report.error("changelog.write", "the rewritten changelog does not contain the new version; refusing to write")
        return report
    write_text(path, new_text)
    report.data["written"] = True
    validation = check(path, report=Report(title="post-write check", root=str(path.parent)), slug=slug)
    if validation.errors:
        report.error("changelog.post-check", f"{len(validation.errors)} error(s) after writing; see findings")
        report.findings.extend(validation.errors)
    return report


def _slug_from_references(references: dict[str, str]) -> str:
    for value in references.values():
        match = re.search(r"github\.com/([^/]+/[^/]+)/", value)
        if match:
            return match.group(1)
    return ""


def _update_references(text: str, version: str, slug: str) -> str:
    lines = text.split("\n")
    if not slug:
        return text
    base = f"https://github.com/{slug}"
    unreleased_index = None
    for index, raw in enumerate(lines):
        match = LINK_REF_RE.match(raw.strip())
        if match and match.group("label").strip().lower() == "unreleased":
            unreleased_index = index
            break
    version_line = f"[{version}]: {base}/compare/v{_previous_version(lines, version)}...v{version}"
    unreleased_line = f"[Unreleased]: {base}/compare/v{version}...HEAD"
    if unreleased_index is not None:
        lines[unreleased_index] = unreleased_line
        lines.insert(unreleased_index + 1, version_line)
    else:
        while lines and not lines[-1].strip():
            lines.pop()
        lines.extend(["", unreleased_line, version_line, ""])
    return "\n".join(lines)


def _previous_version(lines: list[str], current: str) -> str:
    found: list[str] = []
    for raw in lines:
        match = VERSION_RE.match(raw[2:].strip()) if raw.startswith("## ") else None
        if match:
            found.append(match.group("version"))
    if current in found:
        index = found.index(current)
        if index + 1 < len(found):
            return found[index + 1]
    return "0.0.0"


# --------------------------------------------------------------------------
# suggest from commits
# --------------------------------------------------------------------------

def suggest(root: Path, since: str, *, include_noise: bool = False, limit: int = 500,
            report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title=f"ghagent changelog suggest --since {since}", root=str(root))
    rc, out, err = run(["git", "log", f"{since}..HEAD", "--no-merges",
                        "--pretty=format:%H%x1f%s%x1f%b%x1e"], root)
    if rc != 0:
        report.error("git.log", f"git log failed: {err.strip() or 'not a git repository'}")
        return report
    records = [chunk for chunk in out.split("\x1e") if chunk.strip()][:limit]
    if not records:
        report.warn("changelog.suggest-empty", f"no commits between {since} and HEAD")
        return report

    buckets: dict[str, list[str]] = {name: [] for name in TYPES_EN}
    skipped: list[str] = []
    breaking: list[str] = []
    for record in records:
        parts = record.split("\x1f")
        sha = parts[0].strip()[:7]
        subject = parts[1].strip() if len(parts) > 1 else ""
        body = parts[2].strip() if len(parts) > 2 else ""
        match = CONVENTIONAL_RE.match(subject)
        if not match:
            skipped.append(subject)
            continue
        kind = match.group("type").lower()
        if kind in NOISE_TYPES and not include_noise:
            skipped.append(subject)
            continue
        section = TYPE_TO_SECTION.get(kind)
        if section is None:
            skipped.append(subject)
            continue
        description = match.group("description").strip()
        scope = f"**{match.group('scope')}**: " if match.group("scope") else ""
        entry = f"{scope}{description[:1].lower() + description[1:] if description else description}"
        if match.group("breaking") or "BREAKING CHANGE" in body:
            entry = "**Breaking:** " + entry
            breaking.append(subject)
        if not entry.rstrip().endswith("."):
            entry = entry.rstrip() + "."
        buckets[section].append(f"- {entry}")

    lines: list[str] = []
    for name in TYPES_EN:
        if not buckets[name]:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.extend(sorted(set(buckets[name])))
        lines.append("")
    block = "\n".join(lines).strip()
    report.data.update({
        "commits": len(records),
        "entries": sum(len(v) for v in buckets.values()),
        "skipped": len(skipped),
        "breaking": len(breaking),
        "markdown": block,
    })
    if not block:
        report.warn("changelog.suggest-empty", "no commit matched a conventional type that belongs in a changelog",
                    hint="use `feat:`, `fix:`, `perf:`, `docs:`, `security:` prefixes")
    else:
        report.info("changelog.suggest", f"{sum(len(v) for v in buckets.values())} entry(ies) from {len(records)} commit(s)")
    return report


# --------------------------------------------------------------------------
# release notes body
# --------------------------------------------------------------------------

def notes(path: Path, version: str, *, report: Report | None = None) -> Report:
    path = Path(path)
    report = report or Report(title=f"ghagent changelog notes {version}")
    if not path.exists():
        report.error("changelog.missing", f"{path.name} is absent")
        return report
    text, _ = read_text(path)
    versions, _ = parse(text)
    target = next((v for v in versions if v.version == version), None)
    if target is None:
        report.error("changelog.version", f"version {version} is not in the changelog")
        return report
    lines = text.split("\n")
    end = len(lines)
    for later in versions[versions.index(target) + 1:]:
        end = later.line - 1
        break
    body = lines[target.line:end]
    cleaned: list[str] = []
    for raw in body:
        if LINK_REF_RE.match(raw.strip()):
            continue
        cleaned.append(raw)
    block = "\n".join(cleaned).strip()
    report.data.update({"version": version, "date": target.date, "body": block})
    if not block:
        report.error("changelog.empty-version", f"version {version} has an empty body")
    return report
