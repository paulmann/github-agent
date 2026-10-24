"""One report that combines every check the pack can run on a working tree."""

from __future__ import annotations

from pathlib import Path

from . import audit as audit_module
from . import changelog as changelog_module
from . import config as cfg
from . import mdcheck
from . import wiki as wiki_module
from .util import EXIT_FAIL, EXIT_OK, Report, rel


def build(root: Path) -> tuple[str, int]:
    root = Path(root)
    config = cfg.load(root)
    lines: list[str] = [f"# Repository report — {root.name}", "", f"* root: `{root}`"]
    failures = 0

    audit_result = audit_module.audit_local(root, config=config)
    percentage, scored, skipped = audit_result.score()
    lines += [
        "",
        "## 1. Hygiene",
        "",
        f"* score: **{percentage}%** ({scored} scored, {skipped} skipped)",
        f"* errors: {len(audit_result.report.errors)}, warnings: {len(audit_result.report.warnings)}",
        "",
        "| Item | Status | Weight | Detail |",
        "|---|---|---:|---|",
    ]
    for item in audit_result.items:
        lines.append(f"| `{item.ident}` | {item.status} | {item.weight} | {item.detail} |")
    failures += len(audit_result.report.errors)

    doc_report = Report(title="doc", root=str(root))
    checker = mdcheck.DocChecker(root, doc_report, mdcheck.DocCheckOptions(ignore=set(config.ignore_rules)))
    for document in audit_module._primary_documents(root, config):
        checker.check_file(document)
    checker._report_coverage()
    lines += ["", "## 2. Documents", "",
              f"* errors: {len(doc_report.errors)}, warnings: {len(doc_report.warnings)}"]
    for finding in doc_report.findings:
        if finding.level == "error":
            location = f"`{finding.path}:{finding.line}`" if finding.line else f"`{finding.path}`"
            lines.append(f"* **{finding.rule}** {location} — {finding.message}")
    failures += len(doc_report.errors)

    changelog_path = root / config.changelog
    lines += ["", "## 3. Changelog", ""]
    if changelog_path.exists():
        changelog_report = changelog_module.check(changelog_path, slug=config.owner_repo)
        data = changelog_report.data
        lines.append(f"* versions: {data.get('versions', 0)}, latest: `{data.get('latest') or 'none'}`")
        lines.append(f"* pending under Unreleased: {data.get('unreleased_items', 0)}")
        for finding in changelog_report.errors:
            lines.append(f"* **{finding.rule}** — {finding.message}")
        failures += len(changelog_report.errors)
    else:
        lines.append("* CHANGELOG.md is absent")
        failures += 1

    lines += ["", "## 4. Wiki", ""]
    build_dir = root / ".ghagent" / "wiki"
    wiki_source = root / config.wiki_dir
    if wiki_source.is_dir():
        build_report = wiki_module.build(root, wiki_dir=config.wiki_dir,
                                         manifest_path=config.wiki_manifest, out_dir=build_dir)
        if build_report.errors:
            for finding in build_report.errors:
                lines.append(f"* **{finding.rule}** — {finding.message}")
            failures += len(build_report.errors)
        else:
            verify_report = wiki_module.verify(build_dir)
            lines.append(f"* pages built: {verify_report.data.get('pages', 0)}")
            lines.append(f"* internal links: {verify_report.data.get('links_internal', 0)}")
            if verify_report.errors:
                for finding in verify_report.errors:
                    lines.append(f"* **{finding.rule}** — {finding.message}")
                failures += len(verify_report.errors)
            else:
                lines.append("* built tree verified: sidebar, footer, anchors, no relative images")
    else:
        lines.append(f"* no `{config.wiki_dir}/` directory: the wiki is not maintained from the repository")

    lines += ["", "## 5. Verdict", ""]
    lines.append(f"* blocking findings: **{failures}**")
    lines.append("* next step: " + ("fix the errors above" if failures else "ready for review"))
    return "\n".join(lines), (EXIT_FAIL if failures else EXIT_OK)
