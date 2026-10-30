# Architecture

The pack is two layers with one direction of dependency: the CLI knows every command, the
library knows nothing about `argparse`. A command is a thin function that loads configuration,
calls one library entry point and returns the report's exit code. Nothing else happens in the
CLI, so the same behaviour is reachable from `ghagent audit .` (installed console script) and
from `python tools/ghagent.py audit .` (source tree).

```text
argv → ghagent.py (argparse, cmd_* one per command)
         └→ ghalib module (audit, mdcheck, changelog, assets, wiki, meta, install, report)
              └→ Report (findings + data) → text or --json on stdout → exit code
```

## Modules

| Path | Responsibility | Main rule prefixes |
|---|---|---|
| `tools/ghagent.py` | CLI entry point: subparsers, flags, `--json`, exit codes, `selftest` | — |
| `tools/ghalib/util.py` | text I/O (BOM/CRLF detection, atomic UTF-8 LF write), GitHub anchor slugs, markdown structure scanner, `Finding`, `Report` | — |
| `tools/ghalib/config.py` | reads `.ghagent.json` at the repository root; conservative defaults when absent | — |
| `tools/ghalib/mdcheck.py` | UTF-8/BOM/CRLF, headings, tables, fences, alerts, images, links, anchors, TOC, privacy, `agents.md-length` | `doc.*`, `md.*`, `privacy.*` |
| `tools/ghalib/audit.py` | required files, README contract, CHANGELOG contract, AGENTS items, hygiene score; remote metadata through `gh api` | `repo.*`, `readme.*`, `changelog.*`, `agents.*` |
| `tools/ghalib/changelog.py` | Keep a Changelog conformance, promoting `[Unreleased]`, draft from commits, release body | `changelog.*` |
| `tools/ghalib/assets.py` | renders banner SVG (and PNG when Pillow is present), checks references, sizes and dimensions | `assets.*` |
| `tools/ghalib/wiki.py` | manifest-driven build with link rewriting, verify of the built tree, dry-run publication, scaffold | `wiki.*` |
| `tools/ghalib/meta.py` | description and topic validation, merged topic updates through `gh api` | `meta.*` |
| `tools/ghalib/install.py` | copies the pack into an agent skill root, writes a sha256 manifest, verifies drift, removes | `install.*`, `verify.*`, `uninstall.*` |
| `tools/ghalib/report.py` | one markdown report combining hygiene, documents, changelog and wiki | — |

The wheel contains only the CLI layer (`ghagent.py` and `ghalib/`). The pack that a skill root
receives is the source checkout: `skills/`, `tools/`, `tests/`, `reference/`, `wiki/`, `docs/`
and the root documents. That is why `install` and `selftest` are source-tree commands and refuse
in wheel mode instead of pretending to have a suite or a pack.

## Data flow

1. The command resolves the root: the positional path (`audit .`), `--root` (`doc`,
   `privacy`, `assets`, `wiki`, `changelog`, `meta`), or the current directory.
2. `config.load(root)` reads `.ghagent.json`; a missing file means defaults, not an error.
3. The module examines the tree or the remote and appends `Finding` objects to a `Report`.
4. `emit(report, json)` prints the rendered report or its JSON form and returns the exit code.
5. Anything that examined zero objects says so: `coverage.skipped` for a rule, `audit.no-items`
   for a score with no scored items. A green verdict on an empty examination is a defect.

## Exit codes

| Code | Meaning | Typical cause |
|---|---|---|
| `0` | clean | findings are only `warn` or `info` |
| `1` | findings at error level, or an internal error | `doc` reports a broken link; `audit` scores below `--min-score` |
| `2` | usage or environment problem | a path that does not exist, `--size` not `1280x640`, `publish` without a repo, `selftest` without the tests directory |

Warnings never change the exit code. A check that cannot run is exit `2`; a check that ran and
failed is exit `1`; a check that quietly passed nothing is prevented by rule.

## Report and finding model

A `Finding` carries `level` (`error`, `warn`, `info`), `rule` (the id a reader can grep for),
`message`, optional `path`, optional `line`, optional `hint`. Text rendering is one line per
finding, `file:line` included, so a CI log is actionable without opening a browser. `--json`
returns the same findings plus `data`: score, counted items, skipped rules, built-wiki paths,
changed remote fields. The JSON shape is stable enough for another tool to read; the text shape
is for humans.

## Test doctrine

`tests/run_tests.py` is the only test suite, and `ghagent selftest` runs it. The doctrine is
fixture plus decoy:

- **Fixture** — a minimal tree on which a rule must fail with the expected rule id. A rule
  without a failing fixture is not accepted, because it cannot be proven to exist.
- **Decoy** — a neighbouring tree on which the same rule must stay quiet: a lowercase topic
  that must not be flagged, a valid link that must not be "fixed", an SVG that is allowed in a
  README but not as a social preview.
- **Sandbox publication** — the wiki publisher is exercised against a local bare repository, so
  the push path is tested without a network account.

A false `FAIL` is worse than no check; a false `PASS` is worse than a false `FAIL`, because it
buys silence with the appearance of work.

## Why zero dependencies

The pack is installed into an agent's skill directory by copying a directory: no virtual
environment, no build step, no transitive tree that can break the copy. The standard library
supports everything the checks need — `hashlib` for the install manifest, `urllib` for the
optional remote reads, `json` for configuration and reports. Pillow is an extra (`[png]`) and
only changes whether `assets render` writes a PNG next to the SVG. A dependency added to check
links would be the first thing to fail in an air-gapped environment.

## Deliberately out of scope

- Not a code linter. It does not replace `ruff`, `mypy` or a language-specific formatter and will
  not learn them; it reads repository documentation, metadata and the wiki.
- Not a CI service. The Action and the Docker image run the same CLI; there is no server, no
  database and no state beyond the tree and the install manifest.
- No automatic rewriting of a repository's prose. `assets render --write`, `changelog release
  --write`, `meta apply --write`, `install --write` and `wiki build` write only what their names
  say; everything remote stays a dry run without `--push` or `--write`.
- No GitHub administration: no repository creation, visibility change, branch protection, Pages
  deployment, issue triage or dependency updates.
- Network is limited to `audit --repo`, `meta` and `wiki publish`, and every one of them has a
  dry-run or an offline fallback.
