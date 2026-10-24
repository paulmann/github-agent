# AGENTS.md — GitHub repository and wiki steward

Instructions for an agent that runs a GitHub repository and its wiki: audits hygiene, writes
README and AGENTS.md, keeps CHANGELOG, CONTRIBUTING and community files honest, renders the
repository's images, builds and publishes the wiki, and checks links and anchors. Python 3.13,
standard library only — Pillow is optional and only adds PNG output.

This file is the import entry point for **AutoClaw2**, **HARNESS** and **SagaAI**: read it and
you know where the pack lives, how to prove the installation is intact, and which single
command replaces each multi-file investigation.

Language convention: this file and every canonical document are English. Russian copies carry
the `.ru.md` suffix (`README.ru.md`, `AGENTS.ru.md`, `wiki/01-Why.ru.md`). Never edit both and
let them drift — change the English file, then update the translation in the same commit.

## Contents

- [What the pack does](#what-the-pack-does)
- [Quick start](#quick-start)
- [Import into another agent](#import-into-another-agent)
- [Non-negotiable rules](#non-negotiable-rules)
- [Commands](#commands)
- [File contracts](#file-contracts)
- [Images](#images)
- [Workflows](#workflows)
- [Platform traps](#platform-traps)
- [Before you finish](#before-you-finish)
- [Do not](#do-not)
- [Pack layout](#pack-layout)
- [License](#license)

## What the pack does

The same defect repeats in most repositories: a README with no installation section, a
CHANGELOG with no dates, a wiki of three unlinked pages, images that render as broken boxes,
a one-word description. Nothing fails, because `git push` succeeds and no check exists.

The pack turns thirteen recurring jobs into thirteen commands, each returning `0` clean,
`1` with errors, `2` on a usage or environment problem:

| Job | Command | What it examines |
|---|---|---|
| Repository hygiene | `ghagent.py audit` | required files, README and changelog contracts, score |
| Documents | `ghagent.py doc` | BOM/CRLF, headings, tables, links, anchors, TOC |
| Secrets and privacy | `ghagent.py privacy` | tokens, machine paths, personal addresses |
| Images | `ghagent.py assets` | banner, social preview, dimensions, references |
| Wiki | `ghagent.py wiki` | manifest, sidebar, footer, link rewriting, publication |
| Changelog and release | `ghagent.py changelog` | Keep a Changelog conformance, release, notes |
| Metadata | `ghagent.py meta` | description, topics, homepage |
| Skill installation | `ghagent.py install` | copy, sha256 manifest, drift, removal |

## Quick start

```bash
python tools/ghagent.py selftest          # 134 checks, no network
python tools/ghagent.py audit .
python tools/ghagent.py doc --root .
python tools/ghagent.py assets check
```

`selftest` must print `PASS` and exit `0`. If it does not, the copy is not the one that was
tested: reinstall before doing any repository work.

## Import into another agent

| Agent | Skill root | Command |
|---|---|---|
| AutoClaw2 | `%USERPROFILE%\.pi\agent\skills` | `python tools/ghagent.py install --profile autoclaw --write` |
| HARNESS | `%USERPROFILE%\.dsh\skills` | `python tools/ghagent.py install --profile harness --write` |
| SagaAI | supplied by hand | `python tools/ghagent.py install --target <dir> --write` |

The command copies the pack, writes `.install.json` with a sha256 per file, and prints the rules
block to paste into the agent's own `AGENTS.md`. Verify at any time:

```bash
python tools/ghagent.py verify-install --profile autoclaw
```

`verify-install` answers one question: is the installed copy still the one that passed the
tests. Missing or changed files are errors with names, not a vague warning.

## Non-negotiable rules

1. **Only measured numbers.** Every figure in a README, changelog or wiki page names its
   source: a command, a file, an API response. "Fast" and "powerful" are not measurements.
2. **No secrets in published files.** Tokens, keys, absolute machine paths and personal
   addresses are blocking errors (`privacy.*`), not remarks.
3. **No emoji in metadata.** Descriptions, topics and headings are read by search and parsers.
4. **The wiki is a flat namespace.** A page is a file in the wiki repository root; links carry
   no `.md` suffix.
5. **`_Sidebar.md` and `_Footer.md` are mandatory.** Without them a ten-page wiki is a pile.
6. **A relative image cannot work in a wiki.** The wiki is a separate repository and cannot see
   the project tree: commit the image and reference it by absolute URL.
7. **CHANGELOG follows Keep a Changelog 2.0.0.** Six change types, ISO dates, newest first,
   `[Unreleased]` on top, comparison links at the bottom.
8. **Topics: 8–20, lowercase, hyphenated.** `PUT /topics` replaces the whole list — merge with
   the existing set and re-read the response.
9. **Publication only on an explicit flag.** `wiki publish` without `--push` is a dry run;
   `--prune` (deleting remote pages) is a separate human decision.
10. **Commits are signed by the owner**, never by the agent or a bot identity.
11. **A false PASS is worse than a false FAIL.** A rule that examined zero objects says so in
    `coverage.skipped`; an empty tree is `doc.no-text-files`, not success.
12. **English is canonical, Russian is a translation.** `.ru.md` files mirror the English ones
    in the same commit; a translation that lags is a defect.

## Commands

Every command accepts `--json` and `--root <dir>`. Exit codes: `0` clean, `1` findings at
error level, `2` usage or environment problem.

| Task | Command | Flags that change behaviour |
|---|---|---|
| Score a local tree | `ghagent.py audit .` | `--min-score 80` |
| Score GitHub metadata | `ghagent.py audit --repo owner/name` | `--http` checks the homepage |
| Lint markdown | `ghagent.py doc --root .` | `--ignore r1,r2`, `--no-privacy`, `--include-wiki` |
| Scan for leaks | `ghagent.py privacy --root .` | — |
| Render the banner and social preview | `ghagent.py assets render --write` | `--title`, `--tagline`, `--command`, `--chips`, `--size 1280x640` |
| Check images | `ghagent.py assets check` | — |
| Recommend the image set | `ghagent.py assets suggest` | — |
| Build the wiki | `ghagent.py wiki build` | `--out <dir>` |
| Verify the built wiki | `ghagent.py wiki verify` | — |
| Publish the wiki | `ghagent.py wiki publish --repo owner/name --push` | `--prune`, `--force`, `--author-name`, `--author-email` |
| Scaffold a wiki | `ghagent.py wiki init --repo owner/name --title "Name"` | `--no-docs` |
| Check the changelog | `ghagent.py changelog check` | `--repo owner/name` |
| Release a version | `ghagent.py changelog release 1.2.0 --write` | `--date 2026-10-24` |
| Draft entries from commits | `ghagent.py changelog suggest --since v1.1.0` | `--include-noise` |
| Release body | `ghagent.py changelog notes 1.2.0` | — |
| Suggest metadata | `ghagent.py meta suggest` | — |
| Apply metadata | `ghagent.py meta apply --repo owner/name --description "…" --topics a,b --write` | `--replace-topics` |
| One combined report | `ghagent.py report .` | `--out REPORT.md` |

## File contracts

**README.md** — one `H1` under 60 characters; a summary paragraph directly after it; 3–8
badges; a table of contents once the file passes 200 lines; `Installation` (or `Установка`),
`Usage` (or `Быстрый старт`) and `License` sections; a language tag on every code fence; a
column naming the measurement source in every numbers table.

**AGENTS.md** — one `H1`, a purpose paragraph, a table of contents, copy-paste commands, an
explicit verification section, an explicit prohibitions section, and a traps table whose rows
name the symptom that identifies the trap.

**CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/) 2.0.0, and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-10-20

### Added

- Something a user can see.

[Unreleased]: https://github.com/owner/repo/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/owner/repo/compare/v1.0.0...v1.1.0
```

**wiki/wiki.json** — the only ordering authority. A page missing from the manifest is
`wiki.page-unlisted` (error): an unlisted page is invisible in navigation and therefore lost.

```json
{
  "repo": "owner/name",
  "branch": "main",
  "title": "Project name",
  "footer": "MIT",
  "groups": [
    {"title": "Start", "pages": ["Home.md", "01-Install.md"]},
    {"title": "Reference", "pages": ["02-API.md"]}
  ]
}
```

## Images

A repository with no picture reads as abandoned, and the social preview is what link cards
show. The pack renders both from the repository's own metadata and then verifies them.

```bash
python tools/ghagent.py assets render --title "Project" --tagline "What it does, for whom." \
    --command "project --help" --chips "python,github" --write
python tools/ghagent.py assets check
python tools/ghagent.py assets suggest
```

`assets render` writes `assets/social-preview.svg` always and `assets/social-preview.png` when
Pillow is installed. Reference it at the top of the README:

```markdown
<img src="https://github.com/<owner>/<repo>/raw/main/assets/social-preview.png"
     alt="<Project> — <what it does>" width="100%">
```

Rules the checker enforces: the platform accepts PNG, JPG or GIF under 1 MB, at least 640×320,
1280×640 for best display; an SVG works in a README but cannot be uploaded as a social
preview; every referenced file must exist; every image needs alt text; images over `http://`
are warned. The repository copy of the image is *not* the social preview automatically — that
file is uploaded once in **Settings → Social preview**, and the check prints that reminder.

## Workflows

```bash
# audit a repository
python tools/ghagent.py audit . --json > audit.json
python tools/ghagent.py audit --repo owner/name --http
python tools/ghagent.py report . --out AUDIT.md

# release a version
python tools/ghagent.py changelog suggest --since v1.1.0
python tools/ghagent.py changelog release 1.2.0 --write
python tools/ghagent.py changelog check
python tools/ghagent.py changelog notes 1.2.0 > release-body.md

# publish the wiki
python tools/ghagent.py wiki build
python tools/ghagent.py wiki verify
python tools/ghagent.py wiki publish --repo owner/name            # dry run
python tools/ghagent.py wiki publish --repo owner/name --push     # publish
```

`wiki publish` keeps every remote page that the build does not contain and lists them as
`kept`; deletion happens only with `--prune`.

The first publication needs one manual step: `<repo>.wiki.git` does not exist until a first
page is saved in the web interface (Wiki → New page), and a push cannot create it. Until then
`wiki publish --push` returns `wiki.remote-missing` with that instruction.

## Platform traps

| Trap | Symptom | Action |
|---|---|---|
| The wiki repository is not created by a push | `remote: Repository not found` | save the first page in the web interface, then publish |
| Wikis are barely indexed | a page exists but search never shows it | only wikis with 500+ stars and public editing disabled are indexed; use GitHub Pages for discovery |
| A private wiki needs a paid plan | no wiki in a private repository | do not promise it |
| Flat namespace | a link to `docs/page` fails | every page lives in the wiki root |
| Relative image in a wiki | image does not render | commit it and use an absolute raw URL |
| `.md` in a wiki link | raw file or 404 | drop the extension |
| Cyrillic anchors | `#Установка` not found | punctuation is dropped, spaces become hyphens, case is lowered |
| An em dash in a heading | double hyphen in the anchor | the dash is removed; two spaces become two hyphens |
| `PUT /topics` replaces the list | topics you did not touch disappear | merge first, then re-read |
| More than 20 topics | some topics vanish | the API stores 20 |
| Pages for a private repository | `422 Your current plan does not support GitHub Pages for this repository` | the free plan does not allow it |
| Pages builds are asynchronous | 404 right after enabling | poll the build, then the URL |
| `gh api --jq .content` | base64 with line breaks | `-H 'Accept: application/vnd.github.raw'` |
| An SVG as a social preview | upload rejected or blank card | PNG, JPG or GIF only |
| The platform's own anchor example | a lowercase rule contradicted by a capital Greek letter | compare anchors case-insensitively |

## Before you finish

```bash
python tools/ghagent.py selftest
python tools/ghagent.py doc --root .
python tools/ghagent.py audit .
python tools/ghagent.py changelog check
python tools/ghagent.py assets check
python tools/ghagent.py privacy --root .
```

All six must exit `0`. `1` means findings at error level and the command prints them with
`file:line`. `2` means a wrong path or a missing file.

## Do not

- Publish a wiki without `wiki verify` and without reading the dry run.
- Delete remote wiki pages for tidiness; `--prune` is a decision, not a habit.
- Rewrite the changelog from the commit log; `changelog suggest` drafts, a human writes.
- Claim numbers the README does not contain.
- Keep tokens, passwords or personal addresses anywhere in the tree, including examples.
- Sign a commit as the agent.
- Add a dependency to check links. The pack runs on the standard library; Pillow is optional
  and only affects PNG rendering.
- Edit a `.ru.md` file alone and leave the English original behind.

## Pack layout

```text
AGENTS.md          this file: rules, commands, contracts
README.md          the project as a product (English); README.ru.md mirrors it
skills/            repository, wiki, changelog, community, import, images (SKILL.md + .ru.md)
tools/ghagent.py   the single CLI entry point
tools/ghalib/      audit, mdcheck, assets, wiki, changelog, meta, install, report, config
reference/         README, AGENTS, CHANGELOG, CONTRIBUTING, wiki templates and checklists
wiki/              wiki sources: English pages plus .ru.md translations
tests/             self-tests: fixtures, decoys, regressions
docs/              import instructions and procedures
```

## License

MIT — see [LICENSE](LICENSE).
