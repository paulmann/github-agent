"""Repository audit: required files, README contract, changelog contract, promotion metadata.

Two modes:
  * local  — reads a working tree, never touches the network;
  * remote — reads public metadata through `gh api` (or GITHUB_TOKEN) and compares it
             with what the tree claims.

Scoring rule: an item is either pass, fail, warn or not-applicable. Items that could
not be examined are reported as `skipped` and are excluded from both numerator and
denominator, so a network outage lowers coverage instead of raising the score.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import assets as assets_module
from . import config as cfg
from . import mdcheck
from .util import (
    EXIT_FAIL,
    EXIT_OK,
    Report,
    guess_repo_slug,
    read_text,
    rel,
    run,
    scan_structure,
    which,
)

REQUIRED_FILES: list[tuple[str, list[str], int, str]] = [
    ("readme", ["README.md", "README.markdown", "README.rst", "readme.md"], 10, "error"),
    ("license", ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"], 8, "error"),
    ("changelog", ["CHANGELOG.md", "CHANGELOG", "HISTORY.md", "CHANGES.md"], 6, "error"),
    ("contributing", ["CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"], 6, "error"),
    ("security", ["SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md"], 6, "error"),
    ("code-of-conduct", ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md", "docs/CODE_OF_CONDUCT.md"], 4, "warn"),
    ("support", ["SUPPORT.md", ".github/SUPPORT.md"], 2, "warn"),
    ("agents", ["AGENTS.md", ".github/AGENTS.md"], 5, "warn"),
    ("gitattributes", [".gitattributes"], 3, "warn"),
    ("editorconfig", [".editorconfig"], 2, "warn"),
    ("gitignore", [".gitignore"], 3, "warn"),
    ("pr-template", [".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md"], 3, "warn"),
    ("issue-forms", [".github/ISSUE_TEMPLATE", "docs/ISSUE_TEMPLATE"], 4, "warn"),
    ("ci", [".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml"], 6, "warn"),
    ("codeowners", [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"], 2, "warn"),
    ("dependabot", [".github/dependabot.yml", ".github/dependabot.yaml"], 2, "warn"),
    ("citation", ["CITATION.cff", ".github/CITATION.cff"], 2, "info"),
]

BADGE_RE = re.compile(r"!\[[^\]]*\]\(https?://[^)]*\)|\[!\[[^\]]*\]\(https?://[^)]*\)\]\([^)]*\)")
SUPERLATIVES = re.compile(
    r"\b(blazing|revolutionary|best-in-class|world-class|cutting-edge|state-of-the-art|"
    r"amazing|awesome|ultimate|next-gen|game-chang\w+|seamless)\b",
    re.IGNORECASE,
)
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2b00-\u2bff]"
)


@dataclass
class Item:
    ident: str
    title: str
    weight: int
    status: str = "skipped"     # pass | fail | warn | skipped
    detail: str = ""
    severity: str = "error"

    @property
    def scored(self) -> bool:
        return self.status in {"pass", "warn", "fail"}

    @property
    def points(self) -> float:
        if self.status == "pass":
            return self.weight
        if self.status == "warn":
            return self.weight * 0.5
        return 0.0

    def as_dict(self) -> dict:
        return {
            "id": self.ident,
            "title": self.title,
            "weight": self.weight,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class AuditResult:
    report: Report
    items: list[Item] = field(default_factory=list)

    def score(self) -> tuple[float, int, int]:
        scored = [item for item in self.items if item.scored]
        total = sum(item.weight for item in scored)
        got = sum(item.points for item in scored)
        percentage = round(100.0 * got / total, 1) if total else 0.0
        return percentage, len(scored), len([i for i in self.items if not i.scored])


# --------------------------------------------------------------------------
# local audit
# --------------------------------------------------------------------------

def _first_existing(root: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            if path.is_dir():
                if any(path.iterdir()):
                    return path
                continue
            if path.stat().st_size > 0:
                return path
    return None


def audit_local(root: Path, *, config: cfg.Config | None = None, doc_report: Report | None = None) -> AuditResult:
    root = Path(root)
    config = config or cfg.load(root)
    report = Report(title="ghagent audit", root=str(root))
    result = AuditResult(report=report)

    if not root.exists():
        report.error("repo.missing", f"path does not exist: {root}")
        return result

    for ident, candidates, weight, severity in REQUIRED_FILES:
        item = Item(ident=ident, title=candidates[0], weight=weight, severity=severity)
        found = _first_existing(root, candidates)
        if found is None:
            item.status = "fail"
            item.detail = "missing"
            if severity == "info":
                report.info(f"repo.{ident}", f"{candidates[0]} is absent (optional)")
            elif severity == "warn":
                report.warn(f"repo.{ident}", f"{candidates[0]} is absent", hint=f"add {candidates[0]}")
            else:
                report.error(f"repo.{ident}", f"{candidates[0]} is absent", hint=f"add {candidates[0]}")
        else:
            item.status = "pass"
            item.detail = rel(found, root)
        result.items.append(item)

    for extra in config.require_files:
        target = root / extra
        if not target.exists():
            report.error("repo.required-file", f"required by {cfg.CONFIG_NAME}: {extra} is absent")
            result.items.append(Item(ident=f"required:{extra}", title=extra, weight=2, status="fail", detail="missing"))

    readme_path = _first_existing(root, [config.readme, "README.md", "README.markdown"])
    if readme_path is not None:
        result.items.extend(_audit_readme(readme_path, root, report))
    else:
        report.error("readme.missing", "README.md is absent; README contract cannot be examined")

    changelog_path = _first_existing(root, [config.changelog, "CHANGELOG.md", "HISTORY.md"])
    if changelog_path is not None:
        result.items.extend(_audit_changelog(changelog_path, root, report))
    else:
        report.error("changelog.missing", "CHANGELOG.md is absent; changelog contract cannot be examined")

    agents_path = _first_existing(root, [config.agents, "AGENTS.md"])
    if agents_path is not None:
        result.items.extend(_audit_agents(agents_path, root, report))

    wiki_dir = root / config.wiki_dir
    if wiki_dir.is_dir():
        item = Item(ident="wiki-source", title=f"{config.wiki_dir}/", weight=3)
        item.status = "pass"
        item.detail = f"{len(list(wiki_dir.glob('*.md')))} page(s)"
        result.items.append(item)
        manifest = root / config.wiki_manifest
        if not manifest.exists():
            report.warn("wiki.manifest", f"{config.wiki_manifest} is absent",
                        hint="wiki build cannot order pages without a manifest")
    else:
        result.items.append(Item(ident="wiki-source", title=f"{config.wiki_dir}/", weight=3,
                                 status="fail", detail="no wiki source directory"))

    assets_report = assets_module.check(root, report=report)
    reference_item = Item(ident="assets.banner", title="README banner", weight=4)
    if assets_report.data.get("readme_references"):
        reference_item.status = "pass"
        reference_item.detail = f"{assets_report.data['readme_references']} image(s)"
    else:
        reference_item.status = "fail"
        reference_item.detail = "no image in README"
    result.items.append(reference_item)

    social_item = Item(ident="assets.social-preview", title="social preview 1280x640", weight=4)
    if assets_report.data.get("social_preview_ready"):
        social_item.status = "pass"
        social_item.detail = str(assets_report.data.get("social_preview_dimensions"))
    elif assets_report.data.get("social_preview_file"):
        social_item.status = "warn"
        social_item.detail = str(assets_report.data.get("social_preview_dimensions"))
    else:
        social_item.status = "warn"
        social_item.detail = "no assets/social-preview.*"
    result.items.append(social_item)

    if doc_report is None:
        options = mdcheck.DocCheckOptions(ignore=set(config.ignore_rules))
        checker = mdcheck.DocChecker(root, report, options)
        for doc in _primary_documents(root, config):
            checker.check_file(doc)
        checker._report_coverage()
    else:
        report.findings.extend(doc_report.findings)
        report.data.update(doc_report.data)

    percentage, scored, skipped = result.score()
    report.data.update({
        "score": percentage,
        "scored_items": scored,
        "skipped_items": skipped,
        "items": [item.as_dict() for item in result.items],
        "mode": "local",
    })
    if scored == 0:
        report.error("audit.no-items", "no items were examined; the score is meaningless")
    elif percentage < 60:
        report.error("audit.score", f"hygiene score {percentage}% is below 60%")
    elif percentage < 80:
        report.warn("audit.score", f"hygiene score {percentage}% is below 80%")
    return result


def _primary_documents(root: Path, config: cfg.Config) -> list[Path]:
    docs: list[Path] = []
    for name in (config.readme, config.agents, config.changelog, "CONTRIBUTING.md", "SECURITY.md",
                 "CODE_OF_CONDUCT.md", "SUPPORT.md", "GOVERNANCE.md"):
        path = root / name
        if path.exists() and path.suffix.lower() == ".md":
            docs.append(path)
    docs_dir = root / config.docs_dir
    if docs_dir.is_dir():
        docs.extend(sorted(p for p in docs_dir.glob("*.md")))
    return docs


def _audit_readme(path: Path, root: Path, report: Report) -> list[Item]:
    relative = rel(path, root)
    text, _ = read_text(path)
    headings, fences, links, lines = scan_structure(text)
    items: list[Item] = []

    item = Item(ident="readme.h1", title="README has one H1", weight=8)
    h1 = [h for h in headings if h.level == 1]
    if len(h1) == 1:
        item.status = "pass"
        item.detail = h1[0].text
        if len(h1[0].text) > 60:
            report.warn("readme.title", f"H1 is {len(h1[0].text)} characters", path=relative, line=h1[0].line,
                        hint="keep the title under 60 characters")
    elif not h1:
        item.status = "fail"
        item.detail = "no H1"
        report.error("readme.h1", "README has no H1", path=relative, line=1)
    else:
        item.status = "fail"
        item.detail = f"{len(h1)} H1"
        report.error("readme.h1", f"README has {len(h1)} H1 headings", path=relative, line=h1[1].line)
    items.append(item)

    item = Item(ident="readme.summary", title="one-paragraph summary after the title", weight=6)
    body = [raw for raw in lines[h1[0].line:] if raw.strip()] if h1 else []
    summary = body[0].strip() if body else ""
    if summary and not summary.startswith(("#", "!", "[![", "|", ">", "<")):
        item.status = "pass"
        item.detail = summary[:80]
        if EMOJI_RE.search(summary):
            report.warn("readme.emoji", "emoji in the summary line", path=relative, hint="plain words read better in search results")
        if SUPERLATIVES.search(summary):
            report.warn("readme.superlative", "superlative in the summary line", path=relative,
                        hint="state a capability a reader can check")
        if len(summary) > 400:
            report.warn("readme.summary", f"summary paragraph is {len(summary)} characters",
                        path=relative, hint="one or two sentences; details belong in sections")
    else:
        item.status = "fail"
        item.detail = summary[:80] or "no prose after the title"
        report.error("readme.summary", "no summary paragraph directly after the H1", path=relative,
                     hint="one sentence: what it is and for whom")
    items.append(item)

    item = Item(ident="readme.badges", title="at least three badges", weight=5)
    badge_lines = [raw for raw in lines[:40] if BADGE_RE.search(raw)]
    count = len(badge_lines)
    if count >= 3:
        item.status = "pass"
        item.detail = f"{count} badge(s)"
    elif count:
        item.status = "warn"
        item.detail = f"{count} badge(s)"
        report.warn("readme.badges", f"only {count} badge(s)", path=relative, hint="3-8 badges: CI, release, license, runtime")
    else:
        item.status = "fail"
        item.detail = "no badges"
        report.error("readme.badges", "no status badges", path=relative, hint="add CI, release and license badges")
    items.append(item)

    item = Item(ident="readme.toc", title="table of contents", weight=4)
    has_toc = any(h.text.strip().lower().strip(":") in mdcheck.TOC_TITLES for h in headings)
    item.status = "pass" if has_toc else "warn"
    item.detail = "present" if has_toc else "absent"
    if not has_toc:
        report.warn("readme.toc", "no table of contents", path=relative,
                    hint="needed once the README passes ~200 lines")
    items.append(item)

    section_titles = {h.text.strip().lower() for h in headings}
    for ident, weight, aliases, label in [
        ("readme.install", 6, ("installation", "install", "установка", "быстрый старт", "quick start", "getting started"), "installation"),
        ("readme.usage", 6, ("usage", "quick start", "быстрый старт", "использование", "примеры", "examples", "сценарии использования"), "usage"),
        ("readme.license", 5, ("license", "лицензия"), "license"),
    ]:
        item = Item(ident=ident, title=f"{label} section", weight=weight)
        found = any(alias in title for title in section_titles for alias in aliases)
        item.status = "pass" if found else "fail"
        item.detail = "present" if found else "absent"
        if not found:
            report.error(ident, f"README has no {label} section", path=relative,
                         hint=f"add a '## {label.capitalize()}' section")
        items.append(item)

    if "```" in text:
        fences_without_lang = [f for f in fences if f.info == "" and f.closed_at]
        if fences_without_lang:
            report.warn("readme.code-fence", f"{len(fences_without_lang)} fence(s) without a language",
                        path=relative, line=fences_without_lang[0].line)

    for link in links:
        if link.target.startswith("http") and "github.com" in link.target and link.target.endswith((".md",)):
            report.info("readme.absolute-link", f"absolute link to a markdown file: {link.target}",
                        path=relative, line=link.line, hint="a relative link renders in the tree and in the wiki mirror")
    return items


CHANGELOG_ALLOWED_EN = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
CHANGELOG_ALLOWED_RU = ["Добавлено", "Изменено", "Устарело", "Удалено", "Исправлено", "Безопасность"]
VERSION_HEADING_RE = re.compile(
    r"^##\s+\[?(?P<version>\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?)\]?"
    r"(?:\s*[-—–]\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)


def _audit_changelog(path: Path, root: Path, report: Report) -> list[Item]:
    relative = rel(path, root)
    text, _ = read_text(path)
    headings, _, _, lines = scan_structure(text)
    items: list[Item] = []

    item = Item(ident="changelog.versions", title="versions use semantic versioning with ISO dates", weight=6)
    versions = []
    for heading in headings:
        if heading.level != 2:
            continue
        match = VERSION_HEADING_RE.match(f"## {heading.text}")
        if match:
            versions.append((heading, match.group("version"), match.group("date")))
        elif heading.text.strip().strip("[]").lower() not in {"unreleased", "не выпущено", "невыпущено"}:
            report.warn("changelog.heading", f"H2 '{heading.text}' is neither a version nor Unreleased",
                        path=relative, line=heading.line)
    if versions:
        item.status = "pass"
        item.detail = f"{len(versions)} version(s)"
        previous = None
        for heading, version, date in versions:
            if not date:
                report.warn("changelog.date", f"version {version} has no ISO date", path=relative, line=heading.line,
                            hint="## [x.y.z] - YYYY-MM-DD")
            if previous and date and date > previous:
                report.error("changelog.order", f"version {version} is dated after a newer entry",
                             path=relative, line=heading.line, hint="newest release first")
            previous = date or previous
    else:
        item.status = "fail"
        item.detail = "no version heading"
        report.error("changelog.versions", "no '## [x.y.z] - YYYY-MM-DD' heading", path=relative)
    items.append(item)

    item = Item(ident="changelog.unreleased", title="Unreleased section", weight=3)
    has_unreleased = any(h.level == 2 and h.text.strip().strip("[]").lower() in {"unreleased", "не выпущено"} for h in headings)
    item.status = "pass" if has_unreleased else "warn"
    item.detail = "present" if has_unreleased else "absent"
    if not has_unreleased:
        report.warn("changelog.unreleased", "no Unreleased section", path=relative,
                    hint="## [Unreleased] keeps pending work visible")
    items.append(item)

    item = Item(ident="changelog.types", title="change types from the standard set", weight=5)
    allowed = set(CHANGELOG_ALLOWED_EN) | set(CHANGELOG_ALLOWED_RU)
    h3 = [h for h in headings if h.level == 3]
    unknown = [h for h in h3 if h.text.strip() not in allowed]
    if h3 and not unknown:
        item.status = "pass"
        item.detail = f"{len(h3)} typed section(s)"
    elif unknown:
        item.status = "warn"
        item.detail = f"unknown: {', '.join(h.text for h in unknown[:3])}"
        for heading in unknown:
            report.warn("changelog.types", f"unknown change type '{heading.text}'", path=relative, line=heading.line,
                        hint="allowed: " + ", ".join(CHANGELOG_ALLOWED_EN))
    else:
        item.status = "fail"
        item.detail = "no typed subsections"
        report.error("changelog.types", "versions have no Added/Changed/Fixed subsections", path=relative)
    items.append(item)
    return items


def _audit_agents(path: Path, root: Path, report: Report) -> list[Item]:
    relative = rel(path, root)
    text, _ = read_text(path)
    items = [Item(ident="agents.present", title="AGENTS.md present", weight=5, status="pass", detail=relative)]
    lowered = text.lower()
    for ident, needles, weight, label in [
        ("agents.commands", ("```", "`"), 4, "copy-paste commands"),
        ("agents.verify", ("проверк", "verify", "check"), 3, "a verification step"),
        ("agents.traps", ("ловушк", "trap", "не делай", "do not", "запрещ"), 2, "explicit prohibitions"),
    ]:
        item = Item(ident=ident, title=label, weight=weight)
        found = any(needle in lowered for needle in needles)
        item.status = "pass" if found else "warn"
        item.detail = "present" if found else "absent"
        if not found:
            report.warn(ident, f"AGENTS.md has no {label}", path=relative)
        items.append(item)
    return items


# --------------------------------------------------------------------------
# remote audit
# --------------------------------------------------------------------------

def _api(path: str) -> dict | None:
    if which("gh"):
        rc, out, err = run(["gh", "api", path])
        if rc == 0 and out.strip():
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                return None
        if rc != 0 and "gh auth" in err.lower():
            return None
        return None
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return None
    request = urllib.request.Request(
        f"https://api.github.com/{path.lstrip('/')}",
        headers={"User-Agent": "ghagent", "Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None


def audit_remote(slug: str, *, config: cfg.Config | None = None, check_http: bool = False) -> AuditResult:
    report = Report(title=f"ghagent audit --repo {slug}")
    result = AuditResult(report=report)
    repo = _api(f"repos/{slug}")
    if repo is None:
        report.error("remote.unavailable", f"cannot read {slug} through gh api or GITHUB_TOKEN",
                     hint="run `gh auth status`; without metadata no remote item can be examined")
        return result

    description = (repo.get("description") or "").strip()
    topics = repo.get("topics") or []
    homepage = (repo.get("homepage") or "").strip()
    limit = (config or cfg.Config(root=Path("."))).description_max
    topic_min, topic_max = 8, 20
    if config:
        topic_min, topic_max = config.topic_min, config.topic_max

    def item(ident: str, title: str, weight: int, ok: bool, detail: str, level: str = "warn") -> None:
        entry = Item(ident=ident, title=title, weight=weight, status="pass" if ok else "fail", detail=detail)
        result.items.append(entry)
        if not ok:
            report.add(level, ident, detail)

    item("meta.description", "description set", 8, bool(description), f"{len(description)} character(s)", "error")
    if description:
        item("meta.description-length", f"description under {limit} characters", 4, len(description) <= limit,
             f"{len(description)} character(s)")
        lowered = description.lower()
        bad_prefix = lowered.startswith(("a tool", "a simple", "this is", "the tool"))
        item("meta.description-form", "description starts with the category noun", 4, not bad_prefix,
             "starts with a wasted prefix" if bad_prefix else "ok")
        if EMOJI_RE.search(description):
            report.warn("meta.emoji", "emoji in the repository description", hint="descriptions are metadata, not chat")
        if SUPERLATIVES.search(description):
            report.warn("meta.superlative", "superlative in the repository description")
    item("meta.topics-count", f"{topic_min}-{topic_max} topics", 8, topic_min <= len(topics) <= topic_max,
         f"{len(topics)} topic(s)")
    bad_topics = [t for t in topics if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", t)]
    item("meta.topics-form", "topics are lowercase and hyphenated", 4, not bad_topics,
         f"offenders: {', '.join(bad_topics[:5])}" if bad_topics else "ok")
    if len(topics) > 20:
        report.error("meta.topics-overflow", f"{len(topics)} topics requested; the API stores at most 20")
    item("meta.homepage", "homepage set", 4, bool(homepage), homepage or "empty", "info")
    item("wiki.enabled", "wiki enabled", 4, bool(repo.get("has_wiki")), f"has_wiki={repo.get('has_wiki')}", "info")
    license_info = (repo.get("license") or {}).get("spdx_id") or ""
    item("meta.license", "license detected by GitHub", 6, license_info not in ("", "NOASSERTION"),
         license_info or "not detected", "error")
    item("meta.releases", "at least one release", 4, True, "unchecked here", "info")

    releases = _api(f"repos/{slug}/releases?per_page=1")
    if releases is None:
        result.items[-1].status = "skipped"
        report.info("remote.releases", "release list unavailable")
    else:
        result.items[-1] = Item(ident="meta.releases", title="at least one release", weight=4,
                                status="pass" if releases else "warn",
                                detail=f"{len(releases)} release(s) visible")
        if not releases:
            report.warn("meta.releases", "no release: the project reads as unpublished",
                        hint="tag vX.Y.Z with notes from CHANGELOG")

    profile = _api(f"repos/{slug}/community/profile")
    if profile is None:
        report.info("remote.community", "community profile unavailable")
    else:
        percentage = profile.get("health_percentage")
        entry = Item(ident="meta.community-health", title="community health", weight=5,
                     status="pass" if (percentage or 0) >= 80 else "warn",
                     detail=f"{percentage}%")
        result.items.append(entry)
        if (percentage or 0) < 80:
            report.warn("meta.community-health", f"community health {percentage}%",
                        hint="add CODE_OF_CONDUCT, SUPPORT, issue forms, PR template")

    if check_http and homepage:
        ok = _http_ok(homepage)
        item("meta.homepage-live", "homepage returns 200", 4, ok, homepage if ok else "did not answer 200")

    percentage, scored, skipped = result.score()
    report.data.update({
        "score": percentage,
        "scored_items": scored,
        "skipped_items": skipped,
        "items": [i.as_dict() for i in result.items],
        "mode": "remote",
        "repository": {
            "full_name": repo.get("full_name"),
            "description": description,
            "topics": topics,
            "homepage": homepage,
            "has_wiki": repo.get("has_wiki"),
            "has_pages": repo.get("has_pages"),
            "license": license_info,
            "default_branch": repo.get("default_branch"),
        },
    })
    if scored == 0:
        report.error("audit.no-items", "no remote item could be examined")
    return result


def _http_ok(url: str) -> bool:
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ghagent"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 400
    except Exception:  # noqa: BLE001 - any transport failure means "not proven alive"
        return False


# --------------------------------------------------------------------------
# markdown rendering
# --------------------------------------------------------------------------

def render_markdown(result: AuditResult, *, limit: int = 40) -> str:
    report = result.report
    percentage, scored, skipped = result.score()
    lines = [
        f"## Audit — {report.root or report.title}",
        "",
        f"* hygiene score: **{percentage}%** ({scored} item(s) scored, {skipped} skipped)",
        f"* findings: {len(report.errors)} error(s), {len(report.warnings)} warning(s)",
        "",
        "| Item | Status | Weight | Detail |",
        "|---|---|---:|---|",
    ]
    for item in result.items:
        lines.append(f"| `{item.ident}` | {item.status} | {item.weight} | {item.detail} |")
    problems = [f for f in report.findings if f.level in {"error", "warn"}]
    if problems:
        lines += ["", f"### Findings (first {min(limit, len(problems))} of {len(problems)})", ""]
        for finding in problems[:limit]:
            location = f"`{finding.path}:{finding.line}`" if finding.line else (f"`{finding.path}`" if finding.path else "—")
            lines.append(f"* **{finding.level}** `{finding.rule}` {location} — {finding.message}")
    return "\n".join(lines)


def exit_code_for(result: AuditResult) -> int:
    return EXIT_FAIL if result.report.errors else EXIT_OK
