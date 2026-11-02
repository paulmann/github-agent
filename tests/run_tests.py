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
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
sys.path.insert(0, str(PACK / "tools"))

from ghalib import assets as assets_module  # noqa: E402
from ghalib import audit as audit_module  # noqa: E402
from ghalib import changelog as changelog_module  # noqa: E402
from ghalib import install as install_module  # noqa: E402
from ghalib import mdcheck  # noqa: E402
from ghalib import meta as meta_module  # noqa: E402
from ghalib import report as report_module  # noqa: E402
from ghalib import wiki as wiki_module  # noqa: E402
from ghalib.util import (  # noqa: E402
    EXCLUDED_DIRS,
    HIDDEN_DIR_ALLOWLIST,
    PACK_NAME,
    PACK_VERSION,
    Report,
    SlugRegistry,
    force_utf8_stdio,
    git,
    read_text,
    slugify,
    write_text,
)

RESULTS: list[tuple[str, bool, str]] = []
QUIET = "--quiet" in sys.argv


def check(name: str, condition: bool, detail: object = "") -> None:
    """Record one assertion. `detail` may be any value: it is only shown and stored as text."""
    text = "" if detail is None else str(detail)
    RESULTS.append((name, bool(condition), text))
    if not condition and not QUIET:
        print(f"  FAIL  {name}  {text}")


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


def test_wiki_mode(tmp: Path) -> None:
    """A wiki addresses pages by name; a repository addresses files. Both are checked.

    Reported from a real session: `doc --root <wiki checkout>` produced 119 `md.link-local`
    errors on correct links and two `md.h1` errors for `_Sidebar.md`/`_Footer.md`, so the
    only way to run the gate was `--ignore md.link-local,md.h1` — which also switched off
    the real checks.
    """
    root = tmp / "wiki-tree"
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "_Sidebar.md", "- [Home](Home)\n- [Migration](Migration-3.x-to-4.0)\n")
    write_text(root / "_Footer.md", "*Footer text.*\n")
    write_text(root / "Home.md",
               "# Home\n\nSee [Architecture](Architecture) and [migration](Migration-3.x-to-4.0#steps).\n")
    write_text(root / "Architecture.md", "# Architecture\n\n## Security model\n\nText.\n")
    write_text(root / "Migration-3.x-to-4.0.md", "# Migration\n\n## Steps\n\nText.\n")

    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_tree()
    check("wiki: a page-name link resolves inside a wiki checkout", not report.errors,
          "; ".join(f"{f.rule}:{f.message}" for f in report.errors[:4]))
    check("wiki: a page name with dots in it resolves",
          not [f for f in report.findings if f.rule == "md.link-local"],
          str([f.message for f in report.findings if f.rule == "md.link-local"]))
    check("wiki: the partials are a note, not an error",
          all(f.level == "info" for f in report.findings if f.rule == "md.h1"),
          str([(f.level, f.path) for f in report.findings if f.rule == "md.h1"]))

    # The same link outside a wiki is a 404 on GitHub and must stay an error.
    repo = tmp / "plain-repo"
    repo.mkdir(parents=True, exist_ok=True)
    write_text(repo / "Page.md", "# Page\n\nSee [Architecture](Architecture).\n")
    write_text(repo / "Architecture.md", "# Architecture\n\nText.\n")
    report = Report(title="doc", root=str(repo))
    checker = mdcheck.DocChecker(repo, report, mdcheck.DocCheckOptions())
    checker.check_tree()
    expect_rule(report, "md.link-local", "wiki: the same link outside a wiki is still an error")

    # The resolution is not a blanket excuse: a page that does not exist is reported.
    write_text(root / "Home.md", "# Home\n\nSee [Nowhere](Nowhere).\n")
    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_file(root / "Home.md")
    expect_rule(report, "md.link-local", "wiki: a link to a missing page is still an error")


def test_hidden_dirs(tmp: Path) -> None:
    """Tool state is not documentation: `.swarm`, `.zwork`, `.claude` are never published."""
    # The literal paths are assembled at run time: this file is itself checked by the
    # pack's privacy rule, and a machine path written here would be a finding of its own.
    posix_home = "/" + "home/" + "projectowner/project"
    windows_home = "C:" + "\\" + "Users" + "\\" + "projectowner"
    root = tmp / "hidden"
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "README.md", "# Title\n\nText.\n")
    write_text(root / "docs/local.md", f"# Local\n\nWorkspace: {posix_home}\n")
    write_text(root / ".swarm/plan.md", f"Workspace: {posix_home}\n")
    write_text(root / ".zwork/notes.md", f"Path: {windows_home}\n")
    write_text(root / ".github/ISSUE_TEMPLATE/bug.md", "Body starts at H2.\n")

    report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, mdcheck.DocCheckOptions())
    checker.check_tree()
    paths = [f.path for f in report.findings if f.rule == "privacy.abs-path"]
    check("hidden: the published file is still reported", paths == ["docs/local.md"], str(paths))
    files = {str(path.relative_to(root)).replace("\\", "/") for path in mdcheck.iter_text_files(root)}
    check("hidden: the walker skips dot-directories and keeps .github",
          files == {"README.md", "docs/local.md", ".github/ISSUE_TEMPLATE/bug.md"}, str(sorted(files)))


def test_changelog_traps(tmp: Path) -> None:
    """Three findings that turned a correct Keep a Changelog into a red gate."""
    root = tmp / "changelog-traps"
    root.mkdir(parents=True, exist_ok=True)
    body = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "### Added — template language\n\n- A thing.\n\n"
        "## [2.0.0] - 2024-05-01\n\nThe release that rewrote everything.\n\n"
        "## [1.0.0] - 2023-01-01\n\n### Fixed\n\n- A bug.\n"
    )
    write_text(root / "CHANGELOG.md", body)
    report = changelog_module.check(root / "CHANGELOG.md")
    check("changelog: a grouped heading `Added — subtitle` is a known type",
          not [f for f in report.findings if f.rule == "changelog.types"],
          str([f.message for f in report.findings if f.rule == "changelog.types"]))
    check("changelog: missing link references are a warning, not an error",
          not report.errors and any(f.rule == "changelog.link-refs" and f.level == "warn"
                                    for f in report.findings),
          str([(f.rule, f.level) for f in report.findings]))
    check("changelog: a version described in prose is a warning",
          any(f.rule == "changelog.prose-version" and f.level == "warn" for f in report.findings),
          str([(f.rule, f.level) for f in report.findings]))

    # An empty version is still an error: the warning must not swallow a real defect.
    write_text(root / "EMPTY.md",
               "# Changelog\n\n## [1.0.0] - 2024-01-01\n\n## [0.9.0] - 2023-01-01\n\n### Added\n\n- x.\n")
    report = changelog_module.check(root / "EMPTY.md")
    expect_rule(report, "changelog.empty-version", "changelog: a version with no content is still an error")


def test_wiki_verify_target(tmp: Path) -> None:
    """`wiki verify` must verify what the caller named, and say so in the header."""
    repo = tmp / "verify-repo"
    (repo / "wiki").mkdir(parents=True, exist_ok=True)
    write_text(repo / "wiki" / "Home.md", "# Home\n\nText.\n")
    report = wiki_module.verify_target(repo, out=None, wiki_dir="wiki", wiki_dir_given=False)
    check("wiki: sources without a build say `run build`",
          any(f.rule == "wiki.build-missing" for f in report.errors), report.render())

    clone = tmp / "wiki-clone"
    clone.mkdir(parents=True, exist_ok=True)
    write_text(clone / "Home.md", "# Home\n\n[Other](Other)\n")
    write_text(clone / "Other.md", "# Other\n\nText.\n")
    write_text(clone / "_Sidebar.md", "- [Home](Home)\n- [Other](Other)\n")
    write_text(clone / "_Footer.md", "*Footer.*\n")
    report = wiki_module.verify_target(repo, out=None, wiki_dir=str(clone), wiki_dir_given=True)
    check("wiki: --wiki-dir naming a checkout is verified there", not report.errors, report.render())
    check("wiki: the header names the directory that was verified", str(clone) in report.root, report.root)

    empty = tmp / "no-wiki"
    empty.mkdir(parents=True, exist_ok=True)
    report = wiki_module.verify_target(empty, out=None, wiki_dir="wiki", wiki_dir_given=False)
    check("wiki: nothing to verify is a note, not an error",
          not report.errors and any(f.rule == "wiki.not-applicable" for f in report.findings),
          report.render())


def test_meta_remote(tmp: Path) -> None:
    """`meta check --repo` reads the remote; an unreadable remote is not an empty description."""
    import contextlib
    import io

    import ghagent  # the CLI module in tools/

    original = meta_module.read_remote
    meta_module.read_remote = lambda slug: None
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = ghagent.main(["meta", "check", "--repo", "owner/repo"])
    finally:
        meta_module.read_remote = original
    output = buffer.getvalue()
    check("meta: an unreadable remote is an error", code == 1 and "cannot read" in output, output[:300])
    check("meta: the empty field is not claimed without reading", "description is empty" not in output, output[:300])


def test_assets_traps(tmp: Path) -> None:
    """A cut banner is reported, and a two-line title is not called cut."""
    title_lines, title_cut = assets_module._wrap("HTML.PHP — Template Processing Library",
                                                 "mono-bold", 64, 1200, 2)
    check("assets: a two-line title is not reported as cut", len(title_lines) == 2 and not title_cut,
          f"{title_lines} cut={title_cut}")
    tagline_lines, tagline_cut = assets_module._wrap("word " * 60, "sans", 20, 600, 2)
    check("assets: an over-long tagline is reported as cut", tagline_cut,
          f"{tagline_lines} cut={tagline_cut}")
    root = tmp / "assets-traps"
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "README.md", "# Title\n\n**Summary.**\n")
    spec = assets_module.BannerSpec(
        title="A repository title long enough that it cannot fit on two short lines",
        tagline="short")
    report = assets_module.write_assets(root, spec=spec, write=False)
    check("assets: a cut title is a warning, not silence",
          any(f.rule == "assets.truncated" and f.level == "warn" for f in report.findings), report.render())
    check("assets: an empty command line is a note",
          any(f.rule == "assets.no-command" for f in report.findings), report.render())


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
    check("wiki: generated navigation is English",
          "### Links" in sidebar and "[Repository](https://github.com/owner/demo)" in sidebar
          and "[Releases](https://github.com/owner/demo/releases)" in sidebar, sidebar[-400:])
    check("wiki: generated navigation carries no Russian labels",
          "Ссылки" not in sidebar and "Репозиторий" not in sidebar and "Релизы" not in sidebar,
          sidebar[-400:])
    footer, _ = read_text(out / "_Footer.md")
    check("wiki: footer links are absolute", footer.count("https://github.com/owner/demo") >= 2, footer)
    check("wiki: footer is English too",
          "[repository](https://github.com/owner/demo)" in footer
          and "[releases](https://github.com/owner/demo/releases)" in footer
          and "репозиторий" not in footer, footer)
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
    # The expected string comes from the single version source: a literal here would turn every
    # release into a test failure and teach the next reader to edit the test instead of the version.
    expected = f"{PACK_NAME} {PACK_VERSION}"
    check("installed: the CLI itself still works from the installed layout",
          proc.returncode == 0 and expected in proc.stdout,
          f"expected {expected!r} in {proc.stdout + proc.stderr!r}")


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
          "&lt;b&gt;" in assets_module.render_svg(assets_module.BannerSpec(title="a <b> c", tagline="x")),
          assets_module.render_svg(assets_module.BannerSpec(title="a <b> c", tagline="x"))[:300])
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


def test_assets_card(tmp: Path) -> None:
    """The designed card: one layout into PNG and SVG, and only facts the tree can prove.

    Two hard edges are tested here. An auto fact exists only when the tree measures it — an
    unmeasurable license or test count is omitted, never guessed. And the SVG is not a second
    design: it receives the same instruction list as the PNG, coordinate for coordinate.
    """
    # A tree with nothing measurable proves that the renderer omits instead of inventing.
    bare = tmp / "card-bare"
    bare.mkdir()
    write_text(bare / "README.md", "# Bare Project\n\nOne sentence about a bare project.\n")
    bare_labels = {label for label, _value, _source in assets_module.derive_facts(bare)}
    for label in ("license", "version", "test functions", "wiki pages", "doc pages", "runtime deps"):
        check(f"assets: auto facts omit the unmeasurable '{label}'", label not in bare_labels,
              str(sorted(bare_labels)))

    # A tree that declares the facts: each one must name the file it came from.
    measured = tmp / "card-measured"
    (measured / "docs").mkdir(parents=True)
    (measured / "tests").mkdir()
    (measured / "wiki").mkdir()
    write_text(measured / "README.md", "# Measured Tool\n\nA tool that measures itself.\n")
    write_text(measured / "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge.\n")
    write_text(measured / "pyproject.toml",
               '[project]\nname = "measured"\nversion = "2.5.1"\n'
               'description = "A measured tool."\nlicense = "MIT"\ndependencies = []\n\n'
               '[project.scripts]\nmeasured = "measured:main"\n')
    write_text(measured / "docs" / "guide.md", "# Guide\n\nText.\n")
    write_text(measured / "tests" / "test_measured.py",
               "def test_one() -> None:\n    assert True\n\ndef test_two() -> None:\n    assert True\n")
    write_text(measured / "wiki" / "wiki.json",
               '{"repo": "owner/measured", "groups": [{"title": "Start", "pages": ["Home.md"]}]}\n')
    facts = assets_module.derive_facts(measured)
    by_label = {label: value for label, value, _source in facts}
    check("assets: the version fact comes from the manifest", by_label.get("version") == "2.5.1",
          str(by_label))
    check("assets: the license fact comes from the manifest", by_label.get("license") == "MIT",
          str(by_label))
    check("assets: the dependency fact is the declared array length",
          by_label.get("runtime deps") == "0", str(by_label))
    check("assets: the test fact counts the test functions", by_label.get("test functions") == "2",
          str(by_label))
    check("assets: the wiki fact counts the manifest entries", by_label.get("wiki page") == "1",
          str(by_label))
    check("assets: every fact names its source", all(source.strip() for _l, _v, source in facts),
          str(facts))

    # One layout, two renderers: every text instruction lands on the same coordinate in both.
    spec = assets_module.spec_from_repository(measured, title="Measured Tool",
                                              command="measured --help", outputs=["PASS: ok"])
    spec.width, spec.height = assets_module.SOCIAL_SIZE
    card = assets_module.build_card(spec)
    svg = assets_module.render_card_svg(card)
    expected = [(str(element.at[0]), str(element.at[1])) for element in card.elements
                if element.kind in {"text", "duo", "wordmark"}]
    rendered = re.findall(r'<text x="(\d+)" y="(\d+)"', svg)
    check("assets: the SVG twin carries every text at the same coordinate", rendered == expected,
          f"svg={rendered[:4]} card={expected[:4]}")
    check("assets: the wordmark starts with an accent-coloured letter",
          'fill="#4f9cf9">M</tspan>easured' in svg,
          svg[svg.find("<tspan"):svg.find("<tspan") + 160])
    check("assets: the card is a vertical gradient with a terminal panel",
          "linearGradient" in svg and "url(#background)" in svg)
    check("assets: the terminal panel carries traffic lights and real output",
          svg.count("<circle") >= 3 and "measured --help" in svg and "PASS: ok" in svg)
    check("assets: a homepage draws a status dot in the footer",
          assets_module.render_card_svg(assets_module.build_card(
              assets_module.BannerSpec(title="T", footer_right="example.com"))).count("<circle") == 1)

    # A two-word wordmark: one designed gap, one layout used by both renderers. A monospace space
    # cell (42 px at size 76) reads as a double space at display size, so the words are measured
    # once and separated by `WORD_GAP_RATIO`; the remainder therefore starts at the measured
    # prefix width plus exactly that one gap, never at a second space.
    two_card = assets_module.build_card(assets_module.BannerSpec(title="Cert Unifier",
                                                                command="demo --help"))
    wordmark = [element for element in two_card.elements if element.kind == "wordmark"][0]
    layout = assets_module.wordmark_layout(wordmark.text, wordmark.font, wordmark.size)
    check("assets: a two-word wordmark splits into its words",
          [word for word, _x in layout] == ["Cert", "Unifier"], str(layout))
    prefix_width = assets_module.text_width("mono-bold", wordmark.size, "Cert")
    designed_gap = wordmark.size * assets_module.WORD_GAP_RATIO
    check("assets: the remainder starts at the measured prefix plus one gap",
          abs(layout[1][1] - (prefix_width + designed_gap)) <= 1,
          f"layout={layout} prefix={prefix_width} gap={designed_gap}")
    check("assets: the words add up to one measured string",
          abs(assets_module.wordmark_width("Cert Unifier", "mono-bold", wordmark.size)
              - (prefix_width + designed_gap
                 + assets_module.text_width("mono-bold", wordmark.size, "Unifier"))) <= 1,
          f"full={assets_module.wordmark_width('Cert Unifier', 'mono-bold', wordmark.size)}")
    two_svg = assets_module.render_card_svg(two_card)
    two_wordmark_line = next(line for line in two_svg.splitlines()
                             if "<tspan" in line and "Unifier" in line)
    word_positions = [int(value) for value in re.findall(r'<tspan x="(\d+)"', two_wordmark_line)]
    check("assets: the SVG places each word where the layout says",
          word_positions == [wordmark.at[0] + offset for _word, offset in layout],
          f"{word_positions} vs {layout}")
    two_png = assets_module.render_card_png(two_card)
    if two_png is None:
        check("assets: PNG rendering reports the missing dependency", True)
    else:
        from io import BytesIO

        from PIL import Image
        image = Image.open(BytesIO(two_png)).convert("RGB")
        gaps: list[int] = []
        gap_size = 0
        started = False
        for column in range(wordmark.at[0], wordmark.at[0] + 600):
            ink = False
            for row in range(wordmark.at[1] - wordmark.size, wordmark.at[1] + 4):
                pixel = image.getpixel((column, row))
                if isinstance(pixel, tuple) and sum(pixel) > 240:
                    ink = True
                    break
            if ink:
                if started and gap_size:
                    gaps.append(gap_size)
                gap_size = 0
                started = True
            elif started:
                gap_size += 1
        space_cell = assets_module.text_width("mono-bold", wordmark.size, " ")
        word_gap = max(gaps) if gaps else 0
        check("assets: the wordmark keeps one normal word gap, not two spaces",
              0.2 * space_cell < word_gap < 0.95 * space_cell,
              f"gap={word_gap} space={space_cell} gaps={gaps[:8]}")

    png = assets_module.render_card_png(card)
    if png is None:
        check("assets: PNG rendering reports the missing dependency", True)
    else:
        out = tmp / "card-measured.png"
        out.write_bytes(png)
        check("assets: the card PNG is 1280x640",
              assets_module.image_size(out) == assets_module.SOCIAL_SIZE, str(assets_module.image_size(out)))
        check("assets: the card PNG stays under 1 MB", len(png) < assets_module.SOCIAL_MAX_BYTES,
              f"{len(png)} bytes")

    # The dry run says what it drew and where every pill came from.
    report = assets_module.write_assets(measured)
    check("assets: the dry run reports the pills it drew", bool(report.data.get("facts")),
          str(report.data.get("facts")))
    check("assets: the dry run reports a source for every pill",
          all(report.data.get("fact_sources", {}).values()), str(report.data.get("fact_sources")))

    # Explicit facts: --fact turns auto derivation off, --facts auto turns it back on.
    proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "render",
                           "--root", str(measured), "--fact", "tools=40", "--write"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    written_svg, _ = read_text(measured / "assets" / "social-preview.svg")
    check("assets: --fact appears on the card as a value-first pill", "40 tools" in written_svg,
          written_svg[:200])
    check("assets: --fact replaces the auto facts", "MIT license" not in written_svg, written_svg[:200])
    subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "render",
                    "--root", str(measured), "--fact", "tools=40", "--facts", "auto", "--write"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    written_svg, _ = read_text(measured / "assets" / "social-preview.svg")
    check("assets: --facts auto keeps the measured pills next to --fact",
          "40 tools" in written_svg and "MIT license" in written_svg, written_svg[:200])

    # A legacy --chips caller keeps its pills: explicit pills outrank the derived ones.
    legacy = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "render",
                             "--root", str(measured), "--chips", "legacy,chips", "--write"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    written_svg, _ = read_text(measured / "assets" / "social-preview.svg")
    check("assets: --chips keeps its pills when auto facts are on",
          legacy.returncode == 0 and "legacy" in written_svg and "chips" in written_svg,
          written_svg[:200])

    # The six-pill cap is reported, and losing a pill is not an error.
    arguments = [sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "render",
                 "--root", str(measured), "--write"]
    for index in range(8):
        arguments += ["--fact", f"fact{index}={index}"]
    proc = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("assets: more than six pills is reported", "assets.facts-overflow" in proc.stdout,
          proc.stdout[-300:])
    check("assets: a dropped pill is not an error", proc.returncode == 0, f"exit {proc.returncode}")

    # A non-standard size scales the layout instead of cropping it.
    subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "render",
                    "--root", str(measured), "--size", "640x320", "--write"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if assets_module.render_png(assets_module.BannerSpec(title="x")) is not None:
        check("assets: --size 640x320 produces a 640x320 PNG",
              assets_module.image_size(measured / "assets" / "social-preview.png") == (640, 320),
              str(assets_module.image_size(measured / "assets" / "social-preview.png")))

    # A card with neither a command nor output has no terminal panel: the empty box that used to
    # look unfinished is gone and the identity block is centred between rule and footer.
    bare_check = tmp / "card-bare-check"
    bare_check.mkdir()
    write_text(bare_check / "README.md",
               "# Bare Project\n\nOne sentence about a bare project.\n\n"
               "![banner](assets/social-preview.svg)\n")
    bare_render = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets",
                                  "render", "--root", str(bare_check), "--write"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
    bare_svg, _ = read_text(bare_check / "assets" / "social-preview.svg")
    check("assets: no command and no output means no terminal panel",
          bare_render.returncode == 0 and "#0a1018" not in bare_svg and "<circle" not in bare_svg,
          bare_render.stdout[-300:] + bare_render.stderr[-200:])
    check("assets: the missing panel is explained", "assets.no-command" in bare_render.stdout,
          bare_render.stdout[-300:])
    check("assets: the identity block stays on a card without a panel", "Bare Project" in bare_svg,
          bare_svg[:200])
    bare_png = bare_check / "assets" / "social-preview.png"
    # Pillow is optional (`github-agent-cli[png]`): a runner without it writes the SVG only and
    # the PNG assertions below must not turn into a red gate on a machine that never promised one.
    png_supported = assets_module.render_png(assets_module.BannerSpec(title="probe")) is not None
    check("assets: the card without a panel is still 1280x640",
          assets_module.image_size(bare_png) == assets_module.SOCIAL_SIZE or not png_supported,
          str(assets_module.image_size(bare_png)))
    bare_report = assets_module.check(bare_check)
    check("assets: a card without a panel still passes assets check", bare_report.exit_code() == 0,
          "; ".join(f"{finding.rule}: {finding.message}" for finding in bare_report.errors[:4]))

    # Every renderer flag is documented in --help.
    help_proc = subprocess.run([sys.executable, str(PACK / "tools" / "ghagent.py"), "assets", "--help"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
    documented = help_proc.stdout
    flags = ("--title", "--eyebrow", "--summary", "--tagline", "--command", "--output",
             "--output-line", "--fact", "--facts", "--license", "--chips", "--footer-left",
             "--footer-right", "--url", "--homepage", "--accent", "--size", "--out-dir", "--write")
    missing = [flag for flag in flags if flag not in documented]
    check("assets: --help documents every renderer flag", not missing, str(missing))


def test_pack_hygiene() -> None:
    """The pack must ship without BOM, CRLF, machine paths or personal addresses."""
    offenders: list[str] = []
    # Build output and tool state are not part of the published tree: `python -m build` writes
    # its own files, and the gate used to go red for a file nobody ships.
    ignored = set(EXCLUDED_DIRS)
    for path in sorted(PACK.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        directories = path.relative_to(PACK).parts[:-1]
        if any(part in ignored for part in directories):
            continue
        if any(part.startswith(".") and part not in HIDDEN_DIR_ALLOWLIST for part in directories):
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
            ("wiki-mode", lambda: test_wiki_mode(tmp)),
            ("hidden-dirs", lambda: test_hidden_dirs(tmp)),
            ("changelog-traps", lambda: test_changelog_traps(tmp)),
            ("wiki-verify-target", lambda: test_wiki_verify_target(tmp)),
            ("meta-remote", lambda: test_meta_remote(tmp)),
            ("assets-traps", lambda: test_assets_traps(tmp)),
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
            ("assets-card", lambda: test_assets_card(tmp)),
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
