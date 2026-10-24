#!/usr/bin/env python3
"""ghagent — one command per documentation job, so an agent stops reading files by hand.

    ghagent.py audit  [path] [--repo owner/name] [--json] [--http] [--min-score 80]
    ghagent.py doc    [paths...] [--root DIR] [--json] [--ignore RULE,...] [--no-privacy]
    ghagent.py wiki   build|verify|publish|init ...
    ghagent.py changelog check|release|suggest|notes ...
    ghagent.py meta   suggest|apply|check ...
    ghagent.py privacy [path]
    ghagent.py install|verify-install|uninstall --target DIR [--write]
    ghagent.py snippet
    ghagent.py report [path] [--out FILE]
    ghagent.py selftest

Exit codes: 0 clean, 1 findings at error level, 2 usage or environment problem.
Standard library only; no network except `audit --repo`, `meta`, and `wiki publish`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ghalib import assets as assets_module        # noqa: E402
from ghalib import audit as audit_module           # noqa: E402
from ghalib import changelog as changelog_module   # noqa: E402
from ghalib import config as cfg                   # noqa: E402
from ghalib import install as install_module       # noqa: E402
from ghalib import mdcheck                         # noqa: E402
from ghalib import meta as meta_module             # noqa: E402
from ghalib import report as report_module         # noqa: E402
from ghalib import wiki as wiki_module             # noqa: E402
from ghalib.util import (                          # noqa: E402
    EXIT_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    PACK_NAME,
    PACK_VERSION,
    Report,
    emit,
    fail,
    read_text,
    rel,
    write_text,
)


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="machine-readable output")


def _add_ignore(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ignore", default="", help="comma-separated rule ids to skip")


def cmd_assets(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if args.action == "check":
        report = assets_module.check(root)
        return emit(report, args.json)
    if args.action == "suggest":
        report = assets_module.suggest(root)
        return emit(report, args.json)
    if args.action == "render":
        width, _, height = (args.size or "1280x640").partition("x")
        try:
            spec = assets_module.spec_from_repository(
                root,
                title=args.title or "",
                tagline=args.tagline or "",
                command=args.command or "",
                chips=[chip.strip() for chip in args.chips.split(",") if chip.strip()] or None,
            )
            spec.width, spec.height = int(width), int(height)
        except ValueError:
            return fail("--size must look like 1280x640")
        report = assets_module.write_assets(root, out_dir=args.out_dir, spec=spec, write=args.write)
        return emit(report, args.json)
    return fail(f"unknown assets action: {args.action}")


def cmd_audit(args: argparse.Namespace) -> int:
    if args.repo:
        config = cfg.load(Path(args.path))
        result = audit_module.audit_remote(args.repo, config=config, check_http=args.http)
        if args.json:
            print(json.dumps(result.report.as_dict(), ensure_ascii=False, indent=2))
        else:
            percentage, scored, skipped = result.score()
            print(audit_module.render_markdown(result))
            print()
            print(f"score: {percentage}% ({scored} scored, {skipped} skipped)")
        if args.min_score and result.score()[0] < args.min_score:
            print(f"ghagent: score {result.score()[0]}% is below --min-score {args.min_score}", file=sys.stderr)
            return EXIT_FAIL
        return audit_module.exit_code_for(result)

    root = Path(args.path)
    config = cfg.load(root)
    result = audit_module.audit_local(root, config=config)
    percentage, scored, skipped = result.score()
    if args.json:
        print(json.dumps(result.report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(audit_module.render_markdown(result))
        print()
        print(f"score: {percentage}% ({scored} scored, {skipped} skipped)")
    if args.min_score and percentage < args.min_score:
        print(f"ghagent: score {percentage}% is below --min-score {args.min_score}", file=sys.stderr)
        return EXIT_FAIL
    return audit_module.exit_code_for(result)


def cmd_doc(args: argparse.Namespace) -> int:
    root = Path(args.root)
    options = mdcheck.DocCheckOptions(
        ignore={item.strip() for item in args.ignore.split(",") if item.strip()},
        privacy=not args.no_privacy,
        toc=not args.no_toc,
    )
    report = Report(title="ghagent doc", root=str(root))
    checker = mdcheck.DocChecker(root, report, options)
    # Wiki sources use wiki-namespace links (page names without .md); they are checked by
    # `wiki build`/`wiki verify`, not as repository links. Opt in with --include-wiki.
    skip_dirs = {".git", "node_modules", "vendor", ".ghagent", ".venv", "__pycache__"}
    if not args.include_wiki:
        skip_dirs.add("wiki")
    targets = [Path(item) for item in args.paths] if args.paths else sorted(
        path for path in root.rglob("*.md")
        if not (set(path.parts) & skip_dirs)
    )
    if not targets:
        return fail("no markdown files found to check")
    for path in targets:
        checker.check_file(path)
    checker._report_coverage()
    return emit(report, args.json)


def cmd_privacy(args: argparse.Namespace) -> int:
    root = Path(args.root)
    options = mdcheck.DocCheckOptions(privacy=True, toc=False, max_line_rule=False)
    options.ignore = {"doc.bom", "doc.crlf", "doc.final-newline", "doc.tab-indent", "md.h1",
                      "md.heading-skip", "md.fence", "md.table", "md.alert", "md.image-alt",
                      "md.hard-break", "doc.line-length", "md.link-local", "md.toc", "md.link-anchor"}
    report = Report(title="ghagent privacy", root=str(root))
    checker = mdcheck.DocChecker(root, report, options)
    for path in mdcheck.iter_text_files(root):
        checker.check_file(path)
    checker._report_coverage()
    return emit(report, args.json)


def cmd_wiki(args: argparse.Namespace) -> int:
    root = Path(args.root)
    config = cfg.load(root)
    if args.action == "init":
        report = wiki_module.scaffold(root, slug=args.repo or config.owner_repo, title=args.title,
                                      wiki_dir=args.wiki_dir, from_docs=not args.no_docs)
        return emit(report, args.json)
    if args.action == "build":
        report = wiki_module.build(root, wiki_dir=args.wiki_dir, manifest_path=args.manifest,
                                   out_dir=Path(args.out) if args.out else None)
        if not args.json and report.data.get("out"):
            print(f"built {report.data.get('pages')} page(s) into {report.data['out']}")
        return emit(report, args.json)
    if args.action == "verify":
        out = Path(args.out) if args.out else root / ".ghagent" / "wiki"
        report = wiki_module.verify(out)
        return emit(report, args.json)
    if args.action == "publish":
        slug = args.repo or config.owner_repo
        if not slug:
            return fail("publish needs --repo owner/name or repo in the wiki manifest")
        build_dir = Path(args.out) if args.out else root / ".ghagent" / "wiki"
        if not build_dir.exists():
            return fail(f"no built wiki at {build_dir}; run `ghagent wiki build` first")
        verify_report = wiki_module.verify(build_dir)
        if verify_report.errors and not args.force:
            print(verify_report.render())
            print("ghagent: refusing to publish a wiki that fails verification (pass --force only if you accept broken links)",
                  file=sys.stderr)
            return EXIT_FAIL
        report = wiki_module.publish(
            slug, build_dir, push=args.push, prune=args.prune, message=args.message or "",
            author_name=args.author_name or "", author_email=args.author_email or "",
            work_dir=Path(args.workdir) if args.workdir else None,
            remote=args.remote_url or "",
        )
        return emit(report, args.json)
    return fail(f"unknown wiki action: {args.action}")


def cmd_changelog(args: argparse.Namespace) -> int:
    root = Path(args.root)
    config = cfg.load(root)
    path = Path(args.file) if args.file else root / config.changelog
    slug = args.repo or config.owner_repo
    if args.action == "check":
        report = changelog_module.check(path, slug=slug)
        return emit(report, args.json)
    if args.action == "release":
        report = changelog_module.release(path, args.version, date=args.date or "", write=args.write,
                                          slug=slug)
        return emit(report, args.json)
    if args.action == "suggest":
        report = changelog_module.suggest(root, args.since, include_noise=args.include_noise)
        if not args.json and report.data.get("markdown"):
            print(report.render())
            print()
            print(report.data["markdown"])
            return report.exit_code()
        return emit(report, args.json)
    if args.action == "notes":
        report = changelog_module.notes(path, args.version)
        if not args.json and report.data.get("body"):
            print(report.data["body"])
            return report.exit_code()
        return emit(report, args.json)
    return fail(f"unknown changelog action: {args.action}")


def cmd_meta(args: argparse.Namespace) -> int:
    root = Path(args.root)
    config = cfg.load(root)
    if args.action == "suggest":
        facts = meta_module.derive(root)
        topics = meta_module.suggest_topics(facts)
        report = Report(title="ghagent meta suggest", root=str(root))
        for level, rule, message in meta_module.validate_description(facts.get("summary", "")):
            report.add(level, rule, message)
        for level, rule, message in meta_module.check_topics(topics, minimum=config.topic_min,
                                                            maximum=config.topic_max):
            report.add(level, rule, message)
        report.data.update({"facts": facts, "topics": topics,
                            "draft_description": _draft_description(facts)})
        if args.json:
            print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        else:
            print(report.render())
            print()
            print("facts:")
            print(json.dumps(facts, ensure_ascii=False, indent=2))
            print("candidate topics: " + ", ".join(topics))
            print("draft description: " + _draft_description(facts))
        return report.exit_code()
    if args.action == "check":
        report = Report(title="ghagent meta check")
        for level, rule, message in meta_module.validate_description(args.description):
            report.add(level, rule, message)
        topics = [item.strip() for item in args.topics.split(",") if item.strip()]
        for level, rule, message in meta_module.check_topics(topics, minimum=config.topic_min,
                                                            maximum=config.topic_max):
            report.add(level, rule, message)
        return emit(report, args.json)
    if args.action == "apply":
        slug = args.repo or config.owner_repo
        if not slug:
            return fail("meta apply needs --repo owner/name or owner_repo in .ghagent.json")
        topics = [item.strip() for item in args.topics.split(",") if item.strip()] if args.topics else None
        report = meta_module.apply_metadata(
            slug,
            description=args.description,
            topics=topics,
            homepage=args.homepage,
            merge_topics=not args.replace_topics,
            write=args.write,
        )
        return emit(report, args.json)
    return fail(f"unknown meta action: {args.action}")


def _draft_description(facts: dict) -> str:
    title = facts.get("title") or "Project"
    languages = ", ".join(language for language, _count in facts.get("languages", [])[:3])
    summary = facts.get("summary", "").strip()
    runtime = f" {languages.capitalize()}." if languages else ""
    if summary:
        return f"{title}: {summary[:120].rstrip('.')}.{runtime}"
    return f"{title}:{runtime} <add one capability a reader can check>"


def cmd_install(args: argparse.Namespace) -> int:
    target, error = install_module.resolve_target(args.profile, args.target)
    if target is None:
        return fail(error)
    report = install_module.install(HERE.parent, target, write=args.write)
    code = emit(report, args.json)
    if args.write and not args.json:
        print()
        print(install_module.snippet(target))
    return code


def cmd_verify_install(args: argparse.Namespace) -> int:
    target, error = install_module.resolve_target(args.profile, args.target)
    if target is None:
        return fail(error)
    report = install_module.verify(target)
    return emit(report, args.json)


def cmd_uninstall(args: argparse.Namespace) -> int:
    target, error = install_module.resolve_target(args.profile, args.target)
    if target is None:
        return fail(error)
    report = install_module.remove(target, write=args.write)
    return emit(report, args.json)


def cmd_snippet(args: argparse.Namespace) -> int:
    target, error = install_module.resolve_target(args.profile, args.target)
    print(install_module.snippet(target))
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    root = Path(args.root)
    text, code = report_module.build(root)
    if args.out:
        target = Path(args.out)
        if not target.is_absolute():
            target = root / target
        write_text(target, text if text.endswith("\n") else text + "\n")
        print(f"report written to {rel(target, root)}")
    else:
        print(text)
    return code


def cmd_selftest(args: argparse.Namespace) -> int:
    import subprocess
    runner = HERE.parent / "tests" / "run_tests.py"
    if not runner.exists():
        return fail(f"selftest runner is missing: {runner}")
    proc = subprocess.run([sys.executable, str(runner), "--quiet"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print("ghagent: selftest FAILED — the installed copy does not behave as tested", file=sys.stderr)
    else:
        print(f"ghagent {PACK_VERSION} selftest: PASS")
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ghagent", description=f"{PACK_NAME} {PACK_VERSION} — repository and wiki steward")
    parser.add_argument("--version", action="version", version=f"{PACK_NAME} {PACK_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="repository hygiene, README and changelog contracts")
    audit_parser.add_argument("path", nargs="?", default=".")
    audit_parser.add_argument("--repo", default="", help="owner/name: audit the remote metadata instead")
    audit_parser.add_argument("--http", action="store_true", help="also check that the homepage answers")
    audit_parser.add_argument("--min-score", type=float, default=0.0)
    _add_json(audit_parser)
    audit_parser.set_defaults(func=cmd_audit)

    doc_parser = subparsers.add_parser("doc", help="markdown lint, links, anchors, tables, privacy")
    doc_parser.add_argument("paths", nargs="*")
    doc_parser.add_argument("--root", default=".")
    doc_parser.add_argument("--no-privacy", action="store_true")
    doc_parser.add_argument("--no-toc", action="store_true")
    doc_parser.add_argument("--include-wiki", action="store_true", help="also lint the wiki source directory")
    _add_ignore(doc_parser)
    _add_json(doc_parser)
    doc_parser.set_defaults(func=cmd_doc)

    privacy_parser = subparsers.add_parser("privacy", help="secrets, absolute paths, personal addresses")
    privacy_parser.add_argument("--root", default=".")
    _add_json(privacy_parser)
    privacy_parser.set_defaults(func=cmd_privacy)

    assets_parser = subparsers.add_parser("assets", help="banner and social preview: render, check, suggest")
    assets_parser.add_argument("action", choices=["render", "check", "suggest"])
    assets_parser.add_argument("--root", default=".")
    assets_parser.add_argument("--title", default="")
    assets_parser.add_argument("--tagline", default="")
    assets_parser.add_argument("--command", default="")
    assets_parser.add_argument("--chips", default="")
    assets_parser.add_argument("--size", default="1280x640")
    assets_parser.add_argument("--out-dir", default="assets")
    assets_parser.add_argument("--write", action="store_true")
    _add_json(assets_parser)
    assets_parser.set_defaults(func=cmd_assets)

    wiki_parser = subparsers.add_parser("wiki", help="build, verify and publish the GitHub wiki")
    wiki_parser.add_argument("action", choices=["init", "build", "verify", "publish"])
    wiki_parser.add_argument("--root", default=".")
    wiki_parser.add_argument("--repo", default="")
    wiki_parser.add_argument("--title", default="Project")
    wiki_parser.add_argument("--wiki-dir", default="wiki")
    wiki_parser.add_argument("--manifest", default="wiki/wiki.json")
    wiki_parser.add_argument("--out", default="")
    wiki_parser.add_argument("--push", action="store_true", help="actually push to the wiki remote")
    wiki_parser.add_argument("--prune", action="store_true", help="delete remote pages absent from the build")
    wiki_parser.add_argument("--force", action="store_true", help="publish even if verification failed")
    wiki_parser.add_argument("--no-docs", action="store_true")
    wiki_parser.add_argument("--message", default="")
    wiki_parser.add_argument("--author-name", default="")
    wiki_parser.add_argument("--author-email", default="")
    wiki_parser.add_argument("--workdir", default="")
    wiki_parser.add_argument("--remote-url", default="", help="override the wiki remote (testing and mirrors)")
    _add_json(wiki_parser)
    wiki_parser.set_defaults(func=cmd_wiki)

    changelog_parser = subparsers.add_parser("changelog", help="check, release and generate entries")
    changelog_parser.add_argument("action", choices=["check", "release", "suggest", "notes"])
    changelog_parser.add_argument("version", nargs="?", default="")
    changelog_parser.add_argument("--root", default=".")
    changelog_parser.add_argument("--file", default="")
    changelog_parser.add_argument("--repo", default="")
    changelog_parser.add_argument("--date", default="")
    changelog_parser.add_argument("--since", default="")
    changelog_parser.add_argument("--include-noise", action="store_true")
    changelog_parser.add_argument("--write", action="store_true")
    _add_json(changelog_parser)
    changelog_parser.set_defaults(func=cmd_changelog)

    meta_parser = subparsers.add_parser("meta", help="description, topics and homepage")
    meta_parser.add_argument("action", choices=["suggest", "check", "apply"])
    meta_parser.add_argument("--root", default=".")
    meta_parser.add_argument("--repo", default="")
    meta_parser.add_argument("--description", default=None)
    meta_parser.add_argument("--topics", default="")
    meta_parser.add_argument("--homepage", default=None)
    meta_parser.add_argument("--replace-topics", action="store_true")
    meta_parser.add_argument("--write", action="store_true")
    _add_json(meta_parser)
    meta_parser.set_defaults(func=cmd_meta)

    for name, handler, help_text in [
        ("install", cmd_install, "copy the pack into an agent skill root"),
        ("verify-install", cmd_verify_install, "compare an installed copy with its manifest"),
        ("uninstall", cmd_uninstall, "remove an installed pack (needs its manifest)"),
        ("snippet", cmd_snippet, "print the AGENTS.md block that points an agent at this pack"),
    ]:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--profile", default="autoclaw", choices=["autoclaw", "harness", "saga"])
        sub.add_argument("--target", default="")
        sub.add_argument("--write", action="store_true")
        _add_json(sub)
        sub.set_defaults(func=handler)

    report_parser = subparsers.add_parser("report", help="one markdown report from every check")
    report_parser.add_argument("--root", default=".")
    report_parser.add_argument("--out", default="")
    report_parser.set_defaults(func=cmd_report)

    selftest_parser = subparsers.add_parser("selftest", help="run the pack's own test suite")
    selftest_parser.set_defaults(func=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - a traceback is a finding, but exit 1 must still be honest
        print(f"ghagent: internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
