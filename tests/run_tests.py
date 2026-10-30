#!/usr/bin/env python3
"""Self-tests for the github-agent pack. Standard library only, no network.

Every rule that can fail has a fixture that must trigger it, and every rule that
must not fire has a decoy next to it (a `.bak` copy, a file inside node_modules,
a role address instead of a personal one). A rule without a fixture is removed,
not shipped: a check that cannot be proven is worse than no check.

    python tests/run_tests.py [--quiet]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
sys.path.insert(0, str(PACK / "tools"))

from ghalib import audit as audit_module          # noqa: E402
from ghalib import changelog as changelog_module  # noqa: E402
from ghalib import install as install_module      # noqa: E402
from ghalib import mdcheck                        # noqa: E402
from ghalib import meta as meta_module            # noqa: E402
from ghalib import report as report_module        # noqa: E402
from ghalib import wiki as wiki_module            # noqa: E402
from ghalib.util import (                          # noqa: E402
    Report,
    force_utf8_stdio,
    git,
    read_text,
    run,
    scan_structure,
    slugify,
    SlugRegistry,
    write_text,
)

RESULTS: list[tuple[str, bool, str]] = []
QUIET = "--quiet" in sys.argv


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    if not condition and not QUIET:
        print(f"  FAIL  {name}  {detail}")


def expect_rule(report: Report, rule: str, name: str) -> None:
    found = [f for f in report.findings if f.rule == rule]
    check(name, bool(found), f"rule {rule} not reported; got {sorted({f.rule for f in report.findings})}")


def expect_no_rule(report: Report, rule: str, name: str) -> None:
    found = [f for f in report.findings if f.rule == rule]
    check(name, not found, f"rule {rule} fired unexpectedly: {found[0].message if found else ''}")


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def make_tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="ghagent-test-"))


GOOD_README = """# Demo Panel

Panels for a demonstration account: inventory, DNS records and an audit log.

[![CI](https://example.com/ci.svg)](https://example.com)
[![Release](https://example.com/release.svg)](https://example.com)
[![License: MIT](https://example.com/mit.svg)](LICENSE)

## Содержание

- [Что это](#что-это)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Что это

Одна панель вместо десяти скриптов.

```bash
echo ok
```

## Installation

```bash
git clone https://example.com/demo.git
```

## Usage

```bash
python demo.py --help
```

## License

MIT.
"""

GOOD_AGENTS = """# AGENTS.md — инструкции для агентов

## 1. Что это

Панель демонстрационного аккаунта.

## 2. Установка

```bash
git clone https://example.com/demo.git
```

## 3. Проверка

```bash
python tools/ghagent.py audit
```

## 4. Не делай

- Не публикуй вики без проверки.
"""

GOOD_CHANGELOG = """# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Pending work.

## [1.1.0] - 2026-10-20

### Added

- DNS record editor.

### Fixed

- Expiry countdown was off by one day.

## [1.0.0] - 2026-10-01

### Added

- Inventory table.

[Unreleased]: https://github.com/owner/demo/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/owner/demo/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/owner/demo/releases/tag/v1.0.0
"""

GOOD_WIKI_PAGES = {
    "Home.md": "# Demo Panel\n\nНавигация: [установка](01-Install) и [API](../docs/API.md).\n",
    "01-Install.md": "# Установка\n\nСмотри [Home](Home.md) и [API](../docs/API.md#endpoints).\n",
    "02-FAQ.md": "# Вопросы\n\nОтветы ниже.\n\n```bash\necho ok\n```\n",
}


def make_repo(root: Path, *, complete: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "README.md", GOOD_README)
    write_text(root / "AGENTS.md", GOOD_AGENTS)
    write_text(root / "CHANGELOG.md", GOOD_CHANGELOG)
    write_text(root / "CONTRIBUTING.md", "# Участие\n\nПрисылайте pull request.\n")
    write_text(root / "SECURITY.md", "# Безопасность\n\nУязвимости принимаются приватно.\n")
    write_text(root / "LICENSE", "MIT License\n\nCopyright (c) 2026 Demo.\n")
    write_text(root / ".gitattributes", "* text=auto eol=lf\n")
    write_text(root / ".editorconfig", "root = true\n\n[*]\nindent_style = space\nindent_size = 4\n")
    write_text(root / ".gitignore", "build/\n")
    write_text(root / ".github/workflows/ci.yml", "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n")
    write_text(root / ".github/ISSUE_TEMPLATE/bug-report.yml",
               "name: Bug report\ndescription: Something is broken\nbody:\n  - type: textarea\n    id: what\n    attributes:\n      label: What happened\n")
    write_text(root / ".github/PULL_REQUEST_TEMPLATE.md", "## What changed\n\n## How to verify\n")
    write_text(root / ".github/CODEOWNERS", "* @owner\n")
    write_text(root / ".github/dependabot.yml", "version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n    schedule:\n      interval: weekly\n")
    write_text(root / "CITATION.cff", "cff-version: 1.2.0\nmessage: Cite this project\ntitle: Demo Panel\n")
    write_text(root / "docs/API.md", "# API\n\n## Endpoints\n\n| Method | Path |\n|---|---|\n| GET | /health |\n")
    write_text(root / ".ghagent.json", json.dumps({"owner_repo": "owner/demo", "default_branch": "main",
                                                   "require_files": ["docs/API.md"]}, indent=2) + "\n")
    if complete:
        write_text(root / "CODE_OF_CONDUCT.md", "# Кодекс поведения\n\nContributor Covenant 2.1.\n")
        write_text(root / "SUPPORT.md", "# Поддержка\n\nIssues и обсуждения.\n")
        wiki_dir = root / "wiki"
        for name, body in GOOD_WIKI_PAGES.items():
            write_text(wiki_dir / name, body)
        write_text(wiki_dir / "wiki.json", json.dumps({
            "repo": "owner/demo", "branch": "main", "title": "Demo Panel", "footer": "MIT",
            "groups": [
                {"title": "Начало", "pages": ["Home.md", "01-Install.md"]},
                {"title": "Справочник", "pages": ["02-FAQ.md"]},
            ],
        }, ensure_ascii=False, indent=2) + "\n")
    return root


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------

def test_anchors() -> None:
    # Pairs taken from a rendered TOC of a live repository and from the GitHub
    # documentation example. The em dash case proves punctuation is removed and the
    # two surrounding spaces become two hyphens (no collapsing).
    pairs = [
        ("Что это и зачем", "что-это-и-зачем"),
        ("Помочь проекту — фактами, а не активностью", "помочь-проекту--фактами-а-не-активностью"),
        ("MCP для AI-агентов", "mcp-для-ai-агентов"),
        ("Installation", "installation"),
        ("Надёжность и ограничения", "надёжность-и-ограничения"),
        ("This heading is not unique in the file", "this-heading-is-not-unique-in-the-file"),
        ("This'll be a _Helpful_ Section About the Greek Letter Θ!", "thisll-be-a-helpful-section-about-the-greek-letter-θ"),
        ("`code` and **bold**", "code-and-bold"),
        # A Devanagari vowel can be a spacing combining mark (`Mc`, e.g. the candra-o
        # in इंस्टॉलेशन) or a non-spacing one (`Mn`, e.g. the anusvara). GitHub keeps
        # both: a heading and a TOC link written with the same word must agree.
        ("इंस्टॉलेशन", "इंस्टॉलेशन"),
        ("संख्याओं में", "संख्याओं-में"),
        ("कौन-सी जाँचें चलती हैं", "कौन-सी-जाँचें-चलती-हैं"),
        # Latin accented letters are single code points and were never the defect.
        ("Café — résumé", "café--résumé"),
        ("Ελληνικό κείμενο", "ελληνικό-κείμενο"),
        ("Установка (Windows)", "установка-windows"),
    ]
    for heading, expected in pairs:
        check(f"anchor: {heading[:28]}", slugify(heading) == expected, f"got {slugify(heading)!r}, expected {expected!r}")
    registry = SlugRegistry()
    first = registry.add("Sample Section")
    second = registry.add("Sample Section")
    third = registry.add("Sample Section")
    check("anchor: duplicates get -1, -2", (first, second, third) == ("sample-section", "sample-section-1", "sample-section-2"),
          f"got {(first, second, third)}")

    # Document level: the link must resolve, and a wrong anchor must still fail.
    tmp_root = make_tmp()
    try:
        hindi = tmp_root / "hindi"
        write_text(hindi / "good.md",
                   "# शीर्षक\n\n- [इंस्टॉलेशन](#इंस्टॉलेशन)\n\n## इंस्टॉलेशन\n\nपाठ।\n")
        report = Report(title="doc", root=str(hindi))
        checker = mdcheck.DocChecker(hindi, report, mdcheck.DocCheckOptions())
        checker.check_file(hindi / "good.md")
        expect_no_rule(report, "md.link-anchor",
                       "anchor: a Devanagari TOC link resolves against its heading")

        write_text(hindi / "bad.md",
                   "# शीर्षक\n\n- [इंस्टॉलेशन](#इंस्टलेशन)\n\n## इंस्टॉलेशन\n\nपाठ।\n")
        report = Report(title="doc", root=str(hindi))
        checker = mdcheck.DocChecker(hindi, report, mdcheck.DocCheckOptions())
        checker.check_file(hindi / "bad.md")
        expect_rule(report, "md.link-anchor",
                    "anchor: an anchor that lost its vowel sign is reported")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_text_meta(tmp: Path) -> None:
    bom = tmp / "bom.md"
    bom.write_bytes(b"\xef\xbb\xbf# Title\n")
    _text, meta = read_text(bom)
    check("text: BOM detected", meta.has_bom)
    crlf = tmp / "crlf.md"
    crlf.write_bytes(b"# Title\r\n\r\nText.\r\n")
    _text, meta = read_text(crlf)
    check("text: CRLF detected", meta.has_crlf)
    write_text(tmp / "clean.md", "# Title\n\nText.\n")
    raw = (tmp / "clean.md").read_bytes()
    check("text: write_text produces LF without BOM", not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw)


def test_doc_good(tmp: Path) -> None:
    root = make_repo(tmp / "good", complete=True)
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    for name in ("README.md", "AGENTS.md", "CHANGELOG.md", "docs/API.md"):
        checker.check_file(root / name)
    checker._report_coverage()
    check("doc: clean fixture has no errors", not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:4]))
    check("doc: coverage recorded", bool(report.data.get("rules_examined")))


def test_doc_defects(tmp: Path) -> None:
    root = tmp / "defects"
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "a.md", "# Title\n\n## Section\n\n### Sub\n\n| a | b |\n|---|---|\n| 1 | 2 | 3 |\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "a.md")
    expect_rule(report, "md.table", "doc: table row with the wrong cell count")

    write_text(root / "b.md", "# Title\n\n## Два\n\n## Два\n\nSee [missing](nope.md) and [anchor](#nope).\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "b.md")
    expect_rule(report, "md.link-local", "doc: link to a missing file")
    expect_rule(report, "md.link-anchor", "doc: link to a missing anchor")

    write_text(root / "c.md", "# Title\n\n```python\nprint(1)\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "c.md")
    expect_rule(report, "md.fence", "doc: unclosed code fence")

    write_text(root / "d.md", "# Title\n\n## Содержание\n\n- [Есть](#есть)\n- [Нет](#нет)\n\n## Есть\n\nText.\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "d.md")
    expect_rule(report, "md.toc", "doc: table of contents lists a heading that does not exist")

    write_text(root / "e.md", "# Title\n\nText with  still fine.\n")
    (root / "e2.md").write_bytes(b"\xef\xbb\xbf# Title\r\n\r\nText.\r\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "e2.md")
    expect_rule(report, "doc.bom", "doc: BOM reported")
    expect_rule(report, "doc.crlf", "doc: CRLF reported")

    write_text(root / "f.md", "# Title\n\n> [!DANGER]\n> Not a valid alert.\n\n```\nno language\n```\n\n![](image.png)\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "f.md")
    expect_rule(report, "md.alert", "doc: unknown alert type")
    check("doc: fence without language is a warning",
          any(f.rule == "md.fence" and f.level == "warn" for f in report.findings))
    check("doc: image without alt is a warning",
          any(f.rule == "md.image-alt" for f in report.findings))

    # A link written inside inline code is literal text, not a link.
    write_text(root / "g.md", "# Title\n\nПример плохой ссылки: `[API](docs/api.md)` — и всё.\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "g.md")
    expect_no_rule(report, "md.link-local", "doc: a link inside inline code is not checked")

    # The table-of-contents heading itself must not be reported as a missing entry.
    write_text(root / "h.md", "# Title\n\n## Содержание\n\n- [Раз](#раз)\n\n## Раз\n\nText.\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "h.md")
    expect_no_rule(report, "md.toc", "doc: the TOC heading is not its own missing entry")

    # A template may keep unresolved placeholders.
    write_text(root / "template.md", "<!-- ghagent: template -->\n# Title\n\n[link](<docs/missing.md>)\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "template.md")
    expect_no_rule(report, "md.link-local", "doc: a marked template skips link checks")


def test_doc_decoys(tmp: Path) -> None:
    root = tmp / "decoys"
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "good.md", "# Title\n\nText.\n")
    # A broken document inside an excluded directory and a .bak copy must not count.
    write_text(root / "node_modules/pkg/BAD.md", "# One\n\n# Two\n")
    write_text(root / "good.md.bak", "# One\n\n# Two\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_tree()
    check("doc: node_modules and .bak files are not examined", not report.errors,
          "; ".join(f"{f.path}:{f.rule}" for f in report.errors[:3]))
    check("doc: examined exactly one file", report.data.get("rules_examined", {}).get("md.h1") == 1,
          f"md.h1 examined {report.data.get('rules_examined', {}).get('md.h1')}")

    empty = tmp / "empty"
    empty.mkdir()
    report = Report(title="doc", root=str(empty))
    checker = mdcheck.DocChecker(empty, report, mdcheck.DocCheckOptions())
    checker.check_tree()
    expect_rule(report, "doc.no-text-files", "doc: an empty tree is an error, not a silent PASS")

    rule_report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, rule_report, mdcheck.DocCheckOptions(ignore={"md.toc"}))
    checker.check_tree()
    check("doc: --ignore skips a rule", "md.toc" in rule_report.data.get("rules_ignored", []))


def test_agents_md_length(tmp: Path) -> None:
    """`agents.md-length`: the canonical root AGENTS.md is a map, not a manual."""

    def agents_body(lines: int) -> str:
        body = ["# AGENTS.md — instructions for agents", "", "A map of the repository rules.", ""]
        while len(body) < lines:
            body.append(f"Rule {len(body) + 1}: the detail lives in docs/.")
        return "\n".join(body) + "\n"

    root = tmp / "agents-length"
    root.mkdir(parents=True, exist_ok=True)

    write_text(root / "AGENTS.md", agents_body(150))
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "AGENTS.md")
    checker._report_coverage()
    found = [f for f in report.findings if f.rule == "agents.md-length"]
    check("agents: a 150-line root AGENTS.md warns", len(found) == 1 and found[0].level == "warn",
          str([(f.level, f.message) for f in found]))
    check("agents: the warning says the file is a map and points at docs/",
          bool(found) and "docs/" in found[0].hint and "map" in found[0].hint,
          found[0].hint if found else "")
    check("agents: the rule counted the file it examined",
          report.data.get("rules_examined", {}).get("agents.md-length") == 1,
          str(report.data.get("rules_examined", {}).get("agents.md-length")))

    write_text(root / "AGENTS.md", agents_body(121))
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "AGENTS.md")
    expect_rule(report, "agents.md-length", "agents: 121 lines is already over the limit")

    write_text(root / "AGENTS.md", agents_body(120))
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "AGENTS.md")
    expect_no_rule(report, "agents.md-length", "agents: exactly 120 lines stays quiet")

    write_text(root / "AGENTS.md", agents_body(90))
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "AGENTS.md")
    expect_no_rule(report, "agents.md-length", "agents: a 90-line map stays quiet")

    # A long nested copy is a different document with its own contract.
    decoy = tmp / "agents-decoy"
    write_text(decoy / "AGENTS.md", agents_body(90))
    write_text(decoy / "docs" / "AGENTS.md", agents_body(150))
    report = Report(title="doc", root=str(decoy))
    checker = mdcheck.DocChecker(decoy, report, mdcheck.DocCheckOptions())
    checker.check_file(decoy / "AGENTS.md")
    checker.check_file(decoy / "docs" / "AGENTS.md")
    expect_no_rule(report, "agents.md-length", "agents: a long docs/AGENTS.md is not the canonical file")

    # An absent root AGENTS.md is honest coverage, not a crash and not a quiet pass.
    absent = tmp / "agents-absent"
    write_text(absent / "README.md", "# Title\n\nText.\n")
    report = Report(title="doc", root=str(absent))
    checker = mdcheck.DocChecker(absent, report, mdcheck.DocCheckOptions())
    checker.check_tree()
    expect_no_rule(report, "agents.md-length", "agents: an absent root AGENTS.md does not fire")
    check("agents: an absent root AGENTS.md reports skipped coverage",
          any(f.rule == "coverage.skipped" and "agents.md-length" in f.message for f in report.findings),
          str([f.message for f in report.findings if f.rule == "coverage.skipped"]))

    # The CLI flag must silence the rule and say that it did.
    write_text(root / "AGENTS.md", agents_body(150))
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions(ignore={"agents.md-length"}))
    checker.check_file(root / "AGENTS.md")
    checker._report_coverage()
    expect_no_rule(report, "agents.md-length", "agents: --ignore silences the rule")
    check("agents: the ignored rule is listed",
          "agents.md-length" in report.data.get("rules_ignored", []), str(report.data.get("rules_ignored")))

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "doc",
                           "--root", str(root), "--ignore", "agents.md-length"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check("agents: the CLI --ignore flag exits 0 and prints no warning",
          proc.returncode == 0 and "agents.md-length" not in proc.stdout,
          proc.stdout[-300:] + proc.stderr[-200:])


def test_privacy(tmp: Path) -> None:
    root = tmp / "privacy"
    root.mkdir(parents=True, exist_ok=True)
    secret = "gh" + "p_" + "A" * 30
    personal = "person@" + "realdomain.example"
    machine = "C:\\" + "Users\\someone\\project"
    write_text(root / "leak.md", f"# Title\n\ntoken {secret}\n\n{machine}\n\nmail: {personal}\n")
    write_text(root / "safe.md", "# Title\n\nAddress: user@users.noreply.github.com and team@example.com\n")
    report = Report(title="privacy", root=str(root))
    options = mdcheck.DocCheckOptions(privacy=True, toc=False, max_line_rule=False)
    checker = mdcheck.DocChecker(root, report, options)
    checker.check_file(root / "leak.md")
    checker.check_file(root / "safe.md")
    expect_rule(report, "privacy.secret", "privacy: token literal reported")
    expect_rule(report, "privacy.abs-path", "privacy: absolute machine path reported")
    emails = [f for f in report.findings if f.rule == "privacy.email"]
    check("privacy: personal address reported, role/noreply addresses are not",
          len(emails) == 1 and "realdomain" in emails[0].message,
          f"got {[f.message for f in emails]}")


def test_audit(tmp: Path) -> None:
    good = make_repo(tmp / "repo-good", complete=True)
    result = audit_module.audit_local(good)
    percentage, scored, skipped = result.score()
    check("audit: complete repository scores at least 80", percentage >= 80, f"score {percentage}%")
    check("audit: score is computed from examined items", scored >= 20, f"scored {scored}")
    check("audit: complete repository has no errors", not result.report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in result.report.errors[:4]))

    partial = make_repo(tmp / "repo-partial", complete=False)
    (partial / "CHANGELOG.md").unlink()
    result = audit_module.audit_local(partial)
    expect_rule(result.report, "repo.changelog", "audit: missing CHANGELOG is an error")

    bare = tmp / "repo-bare"
    bare.mkdir()
    result = audit_module.audit_local(bare)
    check("audit: an empty tree does not produce a green score",
          bool(result.report.errors) and result.score()[0] < 40,
          f"score {result.score()[0]}%, errors {len(result.report.errors)}")

    decoy = tmp / "repo-decoy"
    decoy.mkdir()
    write_text(decoy / "README.md.bak", GOOD_README)
    result = audit_module.audit_local(decoy)
    expect_rule(result.report, "repo.readme", "audit: README.md.bak does not satisfy the README requirement")

    no_summary = make_repo(tmp / "repo-nosummary")
    write_text(no_summary / "README.md", "# Title\n\n## Содержание\n\n- [Installation](#installation)\n\n## Installation\n\nText.\n\n## Usage\n\nText.\n\n## License\n\nMIT.\n")
    result = audit_module.audit_local(no_summary)
    expect_rule(result.report, "readme.summary", "audit: README without a summary paragraph")

    # An HTML comment is invisible to a reader, so it cannot be the summary: the i18n
    # switcher marker sits directly after the H1 in the translated READMEs.
    commented = make_repo(tmp / "repo-comment")
    write_text(commented / "README.md",
               "# Title\n\n<!-- md-i18n:switcher -->\n\nA summary paragraph a reader can see.\n")
    result = audit_module.audit_local(commented)
    expect_no_rule(result.report, "readme.summary", "audit: a comment before the summary is skipped")

    comment_only = make_repo(tmp / "repo-commentonly")
    write_text(comment_only / "README.md", "# Title\n\n<!-- md-i18n:switcher -->\n")
    result = audit_module.audit_local(comment_only)
    expect_rule(result.report, "readme.summary", "audit: a comment-only block is not a summary")

    no_install = make_repo(tmp / "repo-noinstall")
    write_text(no_install / "README.md", GOOD_README.replace("## Installation", "## Подготовка"))
    result = audit_module.audit_local(no_install)
    expect_rule(result.report, "readme.install", "audit: README without an installation section")


def test_changelog(tmp: Path) -> None:
    good = tmp / "CHANGELOG.md"
    write_text(good, GOOD_CHANGELOG)
    report = changelog_module.check(good, slug="owner/demo")
    check("changelog: clean file passes", not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:4]))
    check("changelog: the preamble after the H1 is read",
          not [f for f in report.findings if f.rule in {"changelog.format-link", "changelog.semver-link"}],
          str([f.rule for f in report.findings]))
    check("changelog: versions counted", report.data.get("versions") == 2, f"got {report.data.get('versions')}")

    no_date = tmp / "CHANGELOG-nodate.md"
    write_text(no_date, GOOD_CHANGELOG.replace("## [1.1.0] - 2026-10-20", "## [1.1.0]"))
    report = changelog_module.check(no_date)
    expect_rule(report, "changelog.date-missing", "changelog: version without a date")

    order = tmp / "CHANGELOG-order.md"
    write_text(order, GOOD_CHANGELOG.replace("## [1.1.0] - 2026-10-20", "## [0.9.0] - 2026-10-20"))
    report = changelog_module.check(order)
    expect_rule(report, "changelog.order", "changelog: versions out of order")

    empty_version = tmp / "CHANGELOG-empty.md"
    write_text(empty_version, "# Changelog\n\n## [1.0.0] - 2026-10-01\n\n## [0.9.0] - 2026-09-01\n\n### Added\n\n- Item.\n")
    report = changelog_module.check(empty_version)
    expect_rule(report, "changelog.empty-version", "changelog: version without entries")

    duplicate = tmp / "CHANGELOG-dup.md"
    write_text(duplicate, GOOD_CHANGELOG + "\n## [1.0.0] - 2026-09-01\n\n### Added\n\n- Again.\n")
    report = changelog_module.check(duplicate)
    expect_rule(report, "changelog.duplicate", "changelog: duplicate version")

    unknown_type = tmp / "CHANGELOG-type.md"
    write_text(unknown_type, "# Changelog\n\n## [1.0.0] - 2026-10-01\n\n### Новинки\n\n- Item.\n")
    report = changelog_module.check(unknown_type)
    check("changelog: unknown change type is a warning",
          any(f.rule == "changelog.types" and f.level == "warn" for f in report.findings))

    release_target = tmp / "CHANGELOG-release.md"
    write_text(release_target, GOOD_CHANGELOG)
    report = changelog_module.release(release_target, "1.2.0", date="2026-10-24", write=True, slug="owner/demo")
    text, _ = read_text(release_target)
    check("changelog: release writes the new version", "## [1.2.0] - 2026-10-24" in text, text[:200])
    check("changelog: release keeps an empty Unreleased section", "## [Unreleased]" in text)
    check("changelog: release moves the entries", "- Pending work." in text.split("## [1.2.0]")[1], "entry not moved")
    check("changelog: release updates the compare link", "[Unreleased]: https://github.com/owner/demo/compare/v1.2.0...HEAD" in text,
          [line for line in text.splitlines() if line.startswith("[Unreleased]")])
    check("changelog: release adds the version link", "[1.2.0]: https://github.com/owner/demo/compare/v1.1.0...v1.2.0" in text)
    check("changelog: release leaves no errors behind", not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:3]))

    report = changelog_module.release(release_target, "1.2.0", date="2026-10-25", write=True)
    expect_rule(report, "changelog.duplicate", "changelog: release refuses an existing version")

    report = changelog_module.notes(release_target, "1.1.0")
    check("changelog: notes extract one section", "DNS record editor" in report.data.get("body", ""),
          report.data.get("body", "")[:80])
    check("changelog: notes contain no link references", "]: http" not in report.data.get("body", ""))

    repo = tmp / "gitrepo"
    repo.mkdir()
    git(["init", "--quiet"], repo)
    git(["config", "user.email", "test@example.com"], repo)
    git(["config", "user.name", "Test"], repo)
    write_text(repo / "root.txt", "0\n")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "chore: initial commit"], repo)
    write_text(repo / "a.txt", "1\n")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "feat(core): add inventory table"], repo)
    write_text(repo / "b.txt", "2\n")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "fix: countdown was off by one day"], repo)
    write_text(repo / "c.txt", "3\n")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "chore: bump deps"], repo)
    report = changelog_module.suggest(repo, "HEAD~3")
    block = report.data.get("markdown", "")
    check("changelog: suggest maps feat to Added", "### Added" in block and "inventory table" in block, block[:120])
    check("changelog: suggest maps fix to Fixed", "### Fixed" in block and "off by one" in block)
    check("changelog: suggest skips chore commits", "bump deps" not in block)


def test_wiki(tmp: Path) -> None:
    root = make_repo(tmp / "wiki-repo", complete=True)
    out = root / ".ghagent" / "wiki"
    report = wiki_module.build(root, out_dir=out)
    check("wiki: build succeeds on the fixture", not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:4]))
    sidebar, _ = read_text(out / "_Sidebar.md")
    check("wiki: sidebar lists the pages without .md", "[Home](Home)" in sidebar and "[02 · FAQ](02-FAQ)" in sidebar,
          sidebar[:200])
    check("wiki: sidebar groups appear", "### Начало" in sidebar and "### Справочник" in sidebar)
    footer, _ = read_text(out / "_Footer.md")
    check("wiki: footer links are absolute", footer.count("https://github.com/owner/demo") >= 2, footer)
    home, _ = read_text(out / "Home.md")
    check("wiki: internal link loses the .md suffix", "](01-Install)" in home, home)
    check("wiki: repository link becomes absolute",
          "https://github.com/owner/demo/blob/main/docs/API.md" in home, home)
    install_page, _ = read_text(out / "01-Install.md")
    check("wiki: anchor survives the rewrite",
          "https://github.com/owner/demo/blob/main/docs/API.md#endpoints" in install_page, install_page)

    verify_report = wiki_module.verify(out)
    check("wiki: built tree verifies", not verify_report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in verify_report.errors[:4]))
    check("wiki: verify does not demand an H1 from the footer",
          not [f for f in verify_report.findings if f.rule == "wiki.no-h1" and f.path == "_Footer.md"],
          str([(f.rule, f.path) for f in verify_report.findings if f.rule == "wiki.no-h1"]))
    check("wiki: verify counted the pages", verify_report.data.get("pages") == 3,
          f"got {verify_report.data.get('pages')}")

    unlisted = make_repo(tmp / "wiki-unlisted", complete=True)
    write_text(unlisted / "wiki" / "03-Extra.md", "# Лишняя\n\nText.\n")
    report = wiki_module.build(unlisted, out_dir=unlisted / ".ghagent" / "wiki")
    expect_rule(report, "wiki.page-unlisted", "wiki: a page missing from the manifest is an error")

    missing = make_repo(tmp / "wiki-missing", complete=True)
    (missing / "wiki" / "02-FAQ.md").unlink()
    report = wiki_module.build(missing, out_dir=missing / ".ghagent" / "wiki")
    expect_rule(report, "wiki.page-missing", "wiki: a manifest entry without a file is an error")

    images = make_repo(tmp / "wiki-image", complete=True)
    write_text(images / "wiki" / "02-FAQ.md", "# Вопросы\n\n![схема](img/scheme.png)\n")
    report = wiki_module.build(images, out_dir=images / ".ghagent" / "wiki")
    expect_rule(report, "wiki.image-relative", "wiki: a relative image is an error")

    literal = make_repo(tmp / "wiki-literal", complete=True)
    write_text(literal / "wiki" / "02-FAQ.md",
               "# Вопросы\n\nПлохой пример: `[API](../docs/API.md)` — так ссылаться нельзя.\n")
    report = wiki_module.build(literal, out_dir=literal / ".ghagent" / "wiki")
    check("wiki: a link inside inline code is left alone",
          not report.errors and "[API](../docs/API.md)" in read_text(literal / ".ghagent" / "wiki" / "02-FAQ.md")[0],
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:3]))

    broken = make_repo(tmp / "wiki-broken", complete=True)
    write_text(broken / "wiki" / "02-FAQ.md", "# Вопросы\n\nСм. [нет страницы](99-Missing.md)\n")
    report = wiki_module.build(broken, out_dir=broken / ".ghagent" / "wiki")
    expect_rule(report, "wiki.link-broken", "wiki: a link to a missing page is an error")

    tampered = make_repo(tmp / "wiki-tampered", complete=True)
    out_tampered = tampered / ".ghagent" / "wiki"
    wiki_module.build(tampered, out_dir=out_tampered)
    write_text(out_tampered / "Home.md", "# Demo\n\nСм. [установку](01-Install.md)\n")
    report = wiki_module.verify(out_tampered)
    expect_rule(report, "wiki.md-suffix", "wiki verify: internal link keeps .md")

    # publish against a local bare repository that already contains a page we must not lose
    remote = tmp / "fake-wiki.git"
    remote.mkdir()
    git(["init", "--bare", "--quiet"], remote)
    seed = tmp / "seed"
    seed.mkdir()
    git(["init", "--quiet"], seed)
    git(["config", "user.email", "test@example.com"], seed)
    git(["config", "user.name", "Test"], seed)
    write_text(seed / "Legacy-Page.md", "# Старая страница\n\nЕё нельзя потерять.\n")
    git(["add", "-A"], seed)
    git(["commit", "--quiet", "-m", "seed"], seed)
    git(["remote", "add", "origin", str(remote)], seed)
    git(["push", "--quiet", "origin", "HEAD:refs/heads/master"], seed)

    report = wiki_module.publish("owner/demo", out, push=False, work_dir=tmp / "publish-missing",
                                remote=str(tmp / "no-such-wiki.git"))
    expect_rule(report, "wiki.remote-missing", "wiki: publishing to a wiki that does not exist is a clear error")
    check("wiki: the missing-remote error explains the platform step",
          any("web" in f.hint for f in report.findings if f.rule == "wiki.remote-missing"))

    work = tmp / "publish-work"
    report = wiki_module.publish("owner/demo", out, push=False, work_dir=work, remote=str(remote),
                                 author_name="Test", author_email="test@example.com")
    check("wiki: dry run does not push", report.data.get("pushed") is False and not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:3]))
    rc, out_text, _ = git(["log", "--oneline", "master"], remote)
    check("wiki: dry run leaves the remote at one commit", len(out_text.strip().splitlines()) == 1, out_text)

    report = wiki_module.publish("owner/demo", out, push=True, work_dir=work / "second", remote=str(remote),
                                 author_name="Test", author_email="test@example.com")
    check("wiki: push succeeds", report.data.get("pushed") is True and not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:3]))
    rc, listing, _ = git(["ls-tree", "--name-only", "master"], remote)
    names = set(listing.split())
    check("wiki: pages arrived on the remote", {"Home.md", "_Sidebar.md", "_Footer.md", "01-Install.md"} <= names, sorted(names))
    check("wiki: a page outside the manifest is preserved", "Legacy-Page.md" in names, sorted(names))
    check("wiki: publish reports what it kept", "Legacy-Page.md" in report.data.get("kept", []), report.data.get("kept"))

    report = wiki_module.publish("owner/demo", out, push=True, prune=True, work_dir=work / "third",
                                 remote=str(remote), author_name="Test", author_email="test@example.com")
    rc, listing, _ = git(["ls-tree", "--name-only", "master"], remote)
    names = set(listing.split())
    check("wiki: --prune deletes pages absent from the manifest", "Legacy-Page.md" not in names, sorted(names))


def test_install(tmp: Path) -> None:
    target = tmp / "skills"
    report = install_module.install(PACK, target, write=True)
    check("install: pack copied", report.data.get("written") is True and not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:3]))
    installed = target / "github-agent"
    check("install: entry points exist", (installed / "AGENTS.md").exists() and (installed / "tools" / "ghagent.py").exists())
    check("install: manifest written", (installed / ".install.json").exists())

    report = install_module.verify(target)
    check("install: verification passes on a fresh copy", not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:3]))

    write_text(installed / "AGENTS.md", "# changed\n")
    report = install_module.verify(target)
    expect_rule(report, "verify.changed", "install: verification catches a modified file")

    other = tmp / "not-ours"
    other.mkdir()
    (other / "github-agent").mkdir()
    report = install_module.remove(other, write=True)
    expect_rule(report, "uninstall.refused", "install: uninstall refuses a directory without a manifest")

    report = install_module.remove(target, write=True)
    check("install: uninstall removes the installed copy", not installed.exists() and not report.errors)


def test_installed_layout(tmp: Path) -> None:
    """A wheel ships the CLI and the library only: the pack commands must refuse honestly.

    The layout is simulated by copying `tools/` into a directory that has no `tests/`
    and no `tools/ghagent.py` next to it — exactly what site-packages looks like.
    """
    site = tmp / "site-packages"
    shutil.copytree(PACK / "tools", site, ignore=shutil.ignore_patterns("__pycache__"))
    entry = site / "ghagent.py"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    def run_entry(*argv: str):
        return subprocess.run([sys.executable, str(entry), *argv], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env)

    proc = run_entry("selftest")
    check("installed: selftest exits 2 without the source tree", proc.returncode == 2,
          f"exit {proc.returncode}: {proc.stdout[-200:]}{proc.stderr[-200:]}")
    check("installed: selftest never prints a PASS it did not measure",
          "PASS" not in proc.stdout + proc.stderr, proc.stdout + proc.stderr)
    check("installed: selftest tells the user to clone the repository",
          "github.com/paulmann/github-agent" in proc.stderr and "tests/run_tests.py" in proc.stderr,
          proc.stderr)

    for command in ("install", "verify-install", "uninstall", "snippet"):
        proc = run_entry(command, "--target", str(tmp / "target"))
        check(f"installed: {command} exits 2 without the source tree", proc.returncode == 2,
              f"exit {proc.returncode}: {proc.stdout[-200:]}{proc.stderr[-200:]}")
        check(f"installed: {command} points at cloning the repository",
              "github.com/paulmann/github-agent" in proc.stderr and "tools/ghagent.py" in proc.stderr,
              proc.stderr)
    check("installed: no skill directory was written", not (tmp / "target").exists())

    proc = run_entry("--version")
    check("installed: the CLI itself still works from the installed layout",
          proc.returncode == 0 and "github-agent 1.2.0" in proc.stdout, proc.stdout + proc.stderr)


def test_meta() -> None:
    check("meta: empty description is an error",
          any(level == "error" for level, _rule, _msg in meta_module.validate_description("")))
    check("meta: wasted prefix is a warning",
          any(rule == "meta.prefix" for _l, rule, _m in meta_module.validate_description("A tool that lists DNS records.")))
    check("meta: superlative is a warning",
          any(rule == "meta.superlative" for _l, rule, _m in meta_module.validate_description("Blazing fast DNS panel.")))
    long_text = "DNS panel: " + "x" * 260
    check("meta: over-long description is a warning",
          any(rule == "meta.length" for _l, rule, _m in meta_module.validate_description(long_text)))
    good = "PHP 8.3 panel: inventory, DNS records and an audit log for one registrar account."
    check("meta: a plain factual description passes",
          not [p for p in meta_module.validate_description(good) if p[0] == "error"],
          str(meta_module.validate_description(good)))
    check("meta: twenty-one topics is an error",
          any(rule == "meta.topics-overflow" for _l, rule, _m in meta_module.check_topics([f"t{i}" for i in range(21)])))
    check("meta: a topic with a space is an error",
          any(rule == "meta.topics-form" for _l, rule, _m in meta_module.check_topics(["bad topic"])))
    check("meta: eight clean topics pass",
          not meta_module.check_topics(["php", "dns", "sqlite", "self-hosted", "cli", "api", "audit", "panel"]))
    check("meta: topic normalisation", meta_module.normalise_topic("GitHub Wiki!") == "github-wiki")


def test_report(tmp: Path) -> None:
    good = make_repo(tmp / "report-good", complete=True)
    text, code = report_module.build(good)
    check("report: complete repository exits 0", code == 0, text.splitlines()[-3:])
    check("report: report mentions the wiki section", "## 4. Wiki" in text)

    bad = make_repo(tmp / "report-bad", complete=True)
    (bad / "CHANGELOG.md").unlink()
    text, code = report_module.build(bad)
    check("report: missing changelog makes the report fail", code == 1)


def test_cli(tmp: Path) -> None:
    good = make_repo(tmp / "cli-good", complete=True)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "doc", "--root", str(good),
                           "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    payload = {}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {}
    check("cli: doc --json exits 0 on a clean tree", proc.returncode == 0, proc.stdout[:200] + proc.stderr[:200])
    check("cli: doc --json returns a findings document", "counts" in payload, proc.stdout[:200])

    write_text(good / "broken.md", "# One\n\n# Two\n")
    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "doc", "--root", str(good)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check("cli: doc exits 1 when a rule fails", proc.returncode == 1, f"exit {proc.returncode}")

    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "--version"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check("cli: --version works", proc.returncode == 0 and "github-agent" in proc.stdout, proc.stdout + proc.stderr)

    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "audit", str(good), "--json"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check("cli: audit --json returns a score", '"score"' in proc.stdout, proc.stdout[:200] + proc.stderr[:200])


def test_stdio_encoding(tmp: Path) -> None:
    """A redirected stdout on Windows uses the locale codec; the CLI must still print.

    PEP 528 makes the console UTF-8, but a pipe or a redirected file is encoded with
    cp1252/cp866/cp1251, none of which can carry an arrow. The guard must switch both
    streams to UTF-8 so a finding is printed instead of UnicodeEncodeError.
    """
    import io

    captured = io.BytesIO()
    stream = io.TextIOWrapper(captured, encoding="cp1252", newline="")
    original = sys.stdout
    sys.stdout = stream
    try:
        force_utf8_stdio()
        print("Settings → Social preview")
        stream.flush()
    finally:
        sys.stdout = original
    check("encoding: a cp1252 stream is switched to UTF-8",
          "Settings → Social preview".encode("utf-8") in captured.getvalue(),
          captured.getvalue()[:120])

    # PYTHONIOENCODING=cp1252 is what Windows does to a redirected pipe; the child must
    # print the non-ASCII hint that `assets check` ends with instead of crashing.
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)
    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"),
                           "assets", "check", "--root", str(PACK)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check("encoding: a redirected cp1252 pipe does not raise an internal error",
          "internal error" not in proc.stderr, proc.stderr[-300:])
    check("encoding: assets check still exits 0 on the pack", proc.returncode == 0,
          f"exit {proc.returncode}: {proc.stdout[-300:]}{proc.stderr[-200:]}")
    check("encoding: the non-ASCII hint arrives intact", "Social preview" in proc.stdout,
          proc.stdout[-300:])


def test_assets(tmp: Path) -> None:
    from ghalib import assets as assets_module

    # Header parsing is dependency-free and must be exact.
    png = assets_module.make_header_png(1280, 640)
    probe = tmp / "probe.png"
    probe.write_bytes(png)
    check("assets: PNG size is read from the header", assets_module.image_size(probe) == (1280, 640),
          str(assets_module.image_size(probe)))
    check("assets: an unknown file yields no size", assets_module.image_size(tmp / "nope.bin") is None)

    spec = assets_module.BannerSpec(title="github-agent", tagline="Repository and wiki steward for AI agents.",
                                    command="ghagent.py audit .", chips=["python", "github"], footer="MIT")
    svg = assets_module.render_svg(spec)
    check("assets: SVG carries the title and the dimensions",
          "github-agent" in svg and 'width="1280"' in svg and svg.strip().endswith("</svg>"))
    check("assets: SVG escapes angle brackets",
          "a &lt;b&gt; c" in assets_module.render_svg(assets_module.BannerSpec(title="a <b> c", tagline="x")),
          assets_module.render_svg(assets_module.BannerSpec(title="a <b> c", tagline="x"))[:200])
    png_bytes = assets_module.render_png(spec)
    if png_bytes is None:
        check("assets: PNG rendering reports the missing dependency", True)
    else:
        out = tmp / "rendered.png"
        out.write_bytes(png_bytes)
        check("assets: rendered PNG is 1280x640", assets_module.image_size(out) == (1280, 640),
              str(assets_module.image_size(out)))
        check("assets: rendered PNG stays under 1 MB", len(png_bytes) < assets_module.SOCIAL_MAX_BYTES,
              f"{len(png_bytes)} bytes")

    # check(): no README image at all is an error, not a quiet pass.
    bare = tmp / "assets-bare"
    bare.mkdir()
    write_text(bare / "README.md", "# Title\n\nText without pictures.\n")
    report = assets_module.check(bare)
    expect_rule(report, "assets.readme-banner", "assets: README without an image is reported")
    check("assets: an absent assets/ directory is a warning",
          any(f.rule == "assets.no-directory" for f in report.findings))

    # A correct pair: PNG at 1280x640 referenced from the README.
    good = tmp / "assets-good"
    (good / "assets").mkdir(parents=True)
    (good / "assets" / "social-preview.png").write_bytes(png)
    write_text(good / "README.md", "# Title\n\nText.\n\n![banner](assets/social-preview.png)\n")
    report = assets_module.check(good)
    check("assets: a 1280x640 preview is accepted", report.data.get("social_preview_ready") is True,
          str(report.data))
    check("assets: the upload hint is stated", any(f.rule == "assets.upload-hint" for f in report.findings))

    # Wrong size, oversized file, SVG as the preview, missing file in the README.
    small = tmp / "assets-small"
    (small / "assets").mkdir(parents=True)
    (small / "assets" / "social-preview.png").write_bytes(assets_module.make_header_png(320, 180))
    write_text(small / "README.md", "# T\n\n![b](assets/social-preview.png)\n")
    expect_rule(assets_module.check(small), "assets.social-dimensions",
                "assets: a preview below 640x320 is an error")

    big = tmp / "assets-big"
    (big / "assets").mkdir(parents=True)
    payload = png + b"\x00" * (assets_module.SOCIAL_MAX_BYTES + 1)
    (big / "assets" / "social-preview.png").write_bytes(payload)
    write_text(big / "README.md", "# T\n\n![b](assets/social-preview.png)\n")
    expect_rule(assets_module.check(big), "assets.social-size", "assets: a file over 1 MB is an error")

    vector = tmp / "assets-svg"
    (vector / "assets").mkdir(parents=True)
    (vector / "assets" / "social-preview.svg").write_bytes(svg.encode("utf-8"))
    write_text(vector / "README.md", "# T\n\n![b](assets/social-preview.svg)\n")
    report = assets_module.check(vector)
    expect_rule(report, "assets.svg-social", "assets: SVG cannot be a social preview")
    check("assets: SVG preview is not reported as ready", report.data.get("social_preview_ready") is False)

    missing = tmp / "assets-missing"
    (missing / "assets").mkdir(parents=True)
    write_text(missing / "README.md", "# T\n\n![b](assets/absent.png)\n")
    expect_rule(assets_module.check(missing), "assets.missing-file",
                "assets: a reference to a missing image is an error")

    # Decoy: an image inside node_modules must not count as the repository preview.
    decoy = tmp / "assets-decoy"
    (decoy / "node_modules" / "pkg").mkdir(parents=True)
    (decoy / "node_modules" / "pkg" / "social-preview.png").write_bytes(png)
    write_text(decoy / "README.md", "# T\n\n![b](node_modules/pkg/social-preview.png)\n")
    report = assets_module.check(decoy)
    check("assets: a preview inside node_modules is not accepted",
          report.data.get("social_preview_ready") is False, str(report.data))

    # http image, alt text and suggest()
    write_text(good / "http.md", "# T\n\n![](http://example.com/x.png)\n")
    report = Report(title="doc", root=str(good))
    checker = mdcheck.DocChecker(good, report, mdcheck.DocCheckOptions())
    checker.check_file(good / "http.md")
    expect_rule(report, "md.image-http", "assets: an image over plain http is reported")
    check("assets: an image without alt text is reported",
          any(f.rule == "md.image-alt" for f in report.findings))

    suggestion = assets_module.suggest(good)
    kinds = [entry["kind"] for entry in suggestion.data.get("recommended", [])]
    check("assets: suggest recommends a banner", "banner" in kinds, str(kinds))

    # The CLI writes both files and reports the size it produced.
    cli_root = tmp / "assets-cli"
    cli_root.mkdir()
    write_text(cli_root / "README.md", "# Cli Demo\n\n**A demo repository for the assets command.**\n")
    write_text(cli_root / "demo.py", "print('ok')\n")
    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "render",
                           "--root", str(cli_root), "--title", "Cli Demo", "--command", "demo --help",
                           "--write"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("assets: CLI render exits 0 and writes the SVG",
          proc.returncode == 0 and (cli_root / "assets" / "social-preview.svg").exists(),
          proc.stdout[-300:] + proc.stderr[-200:])
    check("assets: CLI render also writes a PNG when Pillow is present",
          assets_module.render_png(spec) is None or (cli_root / "assets" / "social-preview.png").exists())


def test_pack_hygiene() -> None:
    """The pack must ship without BOM, CRLF, machine paths or personal addresses."""
    offenders: list[str] = []
    for path in sorted(PACK.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == ".install.json" or ".ghagent" in path.parts:
            continue    # machine-local artefacts, gitignored, never published
        if path.suffix.lower() not in {".md", ".py", ".json", ".yml", ".yaml", ".cff", ".txt", ".toml", ".ini", ".cfg"}:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            offenders.append(f"{path.name}: BOM")
        if b"\r\n" in raw:
            offenders.append(f"{path.name}: CRLF")
    check("pack: every text file is UTF-8 without BOM and uses LF", not offenders, str(offenders[:5]))
    report = Report(title="privacy", root=str(PACK))
    options = mdcheck.DocCheckOptions(privacy=True, toc=False, max_line_rule=False)
    options.ignore = {"md.toc"}
    checker = mdcheck.DocChecker(PACK, report, options)
    for path in mdcheck.iter_text_files(PACK):
        if path.name == ".install.json" or ".ghagent" in path.parts:
            continue
        checker.check_file(path)
    blocked = [f for f in report.findings if f.rule in {"privacy.secret", "privacy.abs-path"}]
    check("pack: no secrets or absolute machine paths", not blocked,
          "; ".join(f"{f.path}:{f.line} {f.rule}" for f in blocked[:4]))


def main() -> int:
    force_utf8_stdio()
    tmp = make_tmp()
    try:
        for name, function in [
            ("anchors", lambda: test_anchors()),
            ("text", lambda: test_text_meta(tmp)),
            ("doc-good", lambda: test_doc_good(tmp)),
            ("doc-defects", lambda: test_doc_defects(tmp)),
            ("doc-decoys", lambda: test_doc_decoys(tmp)),
            ("agents-md-length", lambda: test_agents_md_length(tmp)),
            ("privacy", lambda: test_privacy(tmp)),
            ("audit", lambda: test_audit(tmp)),
            ("changelog", lambda: test_changelog(tmp)),
            ("wiki", lambda: test_wiki(tmp)),
            ("install", lambda: test_install(tmp)),
            ("installed-layout", lambda: test_installed_layout(tmp)),
            ("meta", lambda: test_meta()),
            ("report", lambda: test_report(tmp)),
            ("assets", lambda: test_assets(tmp)),
            ("stdio-encoding", lambda: test_stdio_encoding(tmp)),
            ("cli", lambda: test_cli(tmp)),
            ("pack-hygiene", lambda: test_pack_hygiene()),
        ]:
            if not QUIET:
                print(f"[{name}]")
            try:
                function()
            except Exception:  # noqa: BLE001 - a crashing test is a failure, not a skip
                check(f"{name}: no exception", False, traceback.format_exc(limit=3))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [entry for entry in RESULTS if not entry[1]]
    print()
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("failed:")
        for name, _ok, detail in failed:
            print(f"  - {name}  {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
