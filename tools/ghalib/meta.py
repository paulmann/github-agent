"""Repository metadata: description, topics, homepage.

The tool never invents marketing copy. It (a) derives the factual parts — language,
runtime, existing topics, keywords actually present in the tree — and (b) validates a
human-written description against the rules that decide whether the repository is
findable: keyword first, no wasted prefix, no superlatives, under the truncation limit.

`apply` is dry-run unless `--write` is passed, and it never replaces the whole topic
list: `PUT /repos/{owner}/{repo}/topics` is documented as a replacement, so a careless
call erases topics that were not part of the edit.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

from .util import Report, read_text, run, scan_structure, which

BAD_PREFIXES = ("a tool", "a simple", "a small", "this is", "this repo", "the tool", "tool for")
SUPERLATIVES = re.compile(
    r"\b(blazing|revolutionary|best-in-class|world-class|cutting-edge|state-of-the-art|"
    r"amazing|awesome|ultimate|next-gen|game-chang\w+|seamless|powerful|robust)\b",
    re.IGNORECASE,
)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESCRIPTION_MAX = 200
DESCRIPTION_HARD_MAX = 350
TOPIC_LIMIT = 20

LANGUAGE_BY_SUFFIX = {
    ".php": "php", ".py": "python", ".ps1": "powershell", ".psm1": "powershell",
    ".js": "javascript", ".mjs": "javascript", ".ts": "typescript", ".cs": "csharp",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".java": "java", ".pl": "perl",
    ".sh": "shell", ".bash": "shell", ".sql": "sql", ".css": "css", ".html": "html",
}
MANIFESTS = {
    "pyproject.toml": "python", "package.json": "node", "composer.json": "php",
    "Cargo.toml": "rust", "go.mod": "go", "Gemfile": "ruby", "*.csproj": "dotnet",
}
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you", "are",
    "all", "any", "not", "but", "can", "how", "what", "when", "which", "will", "它的",
    "для", "или", "как", "что", "это", "при", "без", "все", "его", "она", "они", "котор",
    "проект", "проекта", "нужно", "можно", "если", "чтобы", "также",
}


def validate_description(text: str, *, limit: int = DESCRIPTION_MAX) -> list[tuple[str, str, str]]:
    """Return (level, rule, message) tuples for one description string."""
    problems: list[tuple[str, str, str]] = []
    stripped = (text or "").strip()
    if not stripped:
        return [("error", "meta.empty", "description is empty")]
    if len(stripped) > DESCRIPTION_HARD_MAX:
        problems.append(("error", "meta.hard-limit", f"{len(stripped)} characters exceeds the API limit of {DESCRIPTION_HARD_MAX}"))
    elif len(stripped) > limit:
        problems.append(("warn", "meta.length", f"{len(stripped)} characters; search results truncate past {limit}"))
    if stripped.lower().startswith(BAD_PREFIXES):
        problems.append(("warn", "meta.prefix", "starts with a wasted prefix; lead with the category noun"))
    if SUPERLATIVES.search(stripped):
        problems.append(("warn", "meta.superlative", "contains a superlative a reader cannot verify"))
    if EMOJI_RE.search(stripped):
        problems.append(("warn", "meta.emoji", "contains emoji"))
    if not re.search(r"[.:—-]", stripped):
        problems.append(("info", "meta.shape", "no clause separator; state one capability after another"))
    if stripped.endswith(".") and stripped.count(".") < 2:
        problems.append(("info", "meta.shape", "single sentence: name what it is and one capability"))
    return problems


def derive(root: Path) -> dict:
    """Facts the tree can prove: languages, manifests, existing config, title/summary."""
    root = Path(root)
    languages: Counter[str] = Counter()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & {".git", "node_modules", "vendor", ".venv", "__pycache__", "dist", "build", ".ghagent"}:
            continue
        language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
        if language:
            languages[language] += 1
    manifests = [name for name in MANIFESTS if list(root.glob(name))]
    title = ""
    summary = ""
    readme = root / "README.md"
    if readme.exists():
        text, _ = read_text(readme)
        headings, _, _, lines = scan_structure(text)
        h1 = [h for h in headings if h.level == 1]
        title = h1[0].text if h1 else ""
        start = h1[0].line if h1 else 0
        for raw in lines[start:]:
            if raw.strip():
                summary = raw.strip()
                break
    declared: list[str] = []
    for name in ("pyproject.toml", "package.json", "composer.json"):
        candidate = root / name
        if candidate.exists():
            text, _ = read_text(candidate)
            for keyword_section in ("keywords", "topics"):
                for match in re.finditer(rf'"{keyword_section}"\s*:\s*\[([^\]]*)\]', text):
                    declared.extend(re.findall(r'"([^"]+)"', match.group(1)))
    config_file = root / ".ghagent.json"
    configured_topics: list[str] = []
    if config_file.exists():
        data = json.loads(read_text(config_file)[0])
        configured_topics = data.get("topics", [])
    return {
        "languages": languages.most_common(6),
        "manifests": manifests,
        "title": title,
        "summary": summary,
        "declared_keywords": sorted(set(declared))[:20],
        "configured_topics": configured_topics,
    }


def suggest_topics(facts: dict, *, extra: list[str] | None = None) -> list[str]:
    """Build a candidate topic list: technology, platform, use case.

    Order matters — the API preserves it and readers treat the first terms as priority.
    """
    ordered: list[str] = []
    for topic in (extra or []) + facts.get("configured_topics", []):
        topic = normalise_topic(topic)
        if topic and topic not in ordered:
            ordered.append(topic)
    for language, _count in facts.get("languages", []):
        topic = normalise_topic(language)
        if topic and topic not in ordered:
            ordered.append(topic)
    for topic in ("github", "documentation", "cli", "devops"):
        topic = normalise_topic(topic)
        if topic and topic not in ordered:
            ordered.append(topic)
    return ordered[:TOPIC_LIMIT]


def normalise_topic(raw: str) -> str:
    topic = re.sub(r"[^a-zA-Z0-9]+", "-", (raw or "").strip().lower()).strip("-")
    return topic


def check_topics(topics: list[str], *, minimum: int = 8, maximum: int = TOPIC_LIMIT) -> list[tuple[str, str, str]]:
    problems: list[tuple[str, str, str]] = []
    if len(topics) < minimum:
        problems.append(("warn", "meta.topics-count", f"{len(topics)} topic(s); the search surface wants {minimum}-{maximum}"))
    if len(topics) > maximum:
        problems.append(("error", "meta.topics-overflow", f"{len(topics)} topic(s); the API stores at most {maximum}"))
    for topic in topics:
        if not TOPIC_RE.match(topic):
            problems.append(("error", "meta.topics-form", f"'{topic}' is not lowercase-hyphenated"))
        if re.search(r"(19|20)\d\d$", topic):
            problems.append(("warn", "meta.topic-year", f"'{topic}' carries a year, which rots"))
    duplicates = [t for t, count in Counter(topics).items() if count > 1]
    if duplicates:
        problems.append(("warn", "meta.topic-duplicate", f"duplicate topic(s): {', '.join(duplicates)}"))
    return problems


# --------------------------------------------------------------------------
# remote read / write through gh
# --------------------------------------------------------------------------

def _gh(arguments: list[str], payload: dict | None = None) -> tuple[int, str, str]:
    if not which("gh"):
        return 127, "", "gh CLI is not installed"
    command = ["gh", "api", *arguments]
    if payload is not None:
        command += ["--input", "-"]
        try:
            import subprocess
            proc = subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            return proc.returncode, proc.stdout, proc.stderr
        except OSError as exc:
            return 1, "", str(exc)
    rc, out, err = run(command)
    return rc, out, err


def read_remote(slug: str) -> dict | None:
    rc, out, _ = _gh([f"repos/{slug}"])
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def apply_metadata(slug: str, *, description: str | None = None, topics: list[str] | None = None,
                   homepage: str | None = None, merge_topics: bool = True, write: bool = False,
                   report: Report | None = None) -> Report:
    report = report or Report(title=f"ghagent meta apply {slug}")
    current = read_remote(slug)
    if current is None:
        report.error("meta.remote", f"cannot read {slug} through gh api", hint="run `gh auth status`")
        return report

    before = {
        "description": (current.get("description") or "").strip(),
        "topics": current.get("topics") or [],
        "homepage": (current.get("homepage") or "").strip(),
    }
    changes: dict[str, dict] = {}

    if description is not None:
        for level, rule, message in validate_description(description):
            report.add(level, rule, message)
        if description.strip() and description != before["description"]:
            changes["description"] = {"from": before["description"], "to": description.strip()}
    if homepage is not None and homepage != before["homepage"]:
        changes["homepage"] = {"from": before["homepage"], "to": homepage.strip()}
    if topics is not None:
        merged = list(before["topics"]) if merge_topics else []
        for topic in topics:
            normalised = normalise_topic(topic)
            if normalised and normalised not in merged:
                merged.append(normalised)
        for level, rule, message in check_topics(merged):
            report.add(level, rule, message)
        if merged[:TOPIC_LIMIT] != before["topics"]:
            changes["topics"] = {"from": before["topics"], "to": merged[:TOPIC_LIMIT]}

    report.data.update({"before": before, "changes": changes, "written": False})
    if not changes:
        report.info("meta.no-change", "nothing to change: the remote already matches the request")
        return report
    if not write:
        report.info("meta.dry-run", f"would change {', '.join(sorted(changes))}", hint="pass --write to apply")
        return report
    if report.errors:
        report.error("meta.refused", "not applied: validation produced errors")
        return report

    if "description" in changes or "homepage" in changes:
        payload = {}
        if "description" in changes:
            payload["description"] = changes["description"]["to"]
        if "homepage" in changes:
            payload["homepage"] = changes["homepage"]["to"]
        rc, out, err = _gh(["-X", "PATCH", f"repos/{slug}"], payload)
        if rc != 0:
            report.error("meta.patch", f"PATCH failed: {err.strip()[:300]}")
            return report
    if "topics" in changes:
        rc, out, err = _gh(["-X", "PUT", f"repos/{slug}/topics"], {"names": changes["topics"]["to"]})
        if rc != 0:
            report.error("meta.topics-put", f"PUT topics failed: {err.strip()[:300]}")
            return report

    after = read_remote(slug) or {}
    report.data["after"] = {
        "description": (after.get("description") or "").strip(),
        "topics": after.get("topics") or [],
        "homepage": (after.get("homepage") or "").strip(),
    }
    report.data["written"] = True
    for field_name in ("description", "homepage"):
        if field_name in changes and report.data["after"][field_name] != changes[field_name]["to"]:
            report.error("meta.verify", f"{field_name} did not change on the remote")
    if "topics" in changes and sorted(report.data["after"]["topics"]) != sorted(changes["topics"]["to"]):
        report.warn("meta.verify", "the stored topic list differs from the requested one",
                    hint="the API may truncate or reorder; re-read before claiming success")
    return report
