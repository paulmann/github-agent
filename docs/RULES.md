# Rules

This is the full rule catalogue behind [AGENTS.md](../AGENTS.md). The short file tells an agent
what to do; this file records what is checked, how, and why, so that a rule is never "because it
says so". Every finding carries a rule id: grep it here, run the command named in the last
column, read the finding with `file:line`.

One principle outranks the list: a false `PASS` is worse than a false `FAIL`. A rule that
examined zero objects reports `coverage.skipped`; a check that could not run exits `2`, not `0`.

## Enforcement map

| Rule id prefix | Command that produces it | Module |
|---|---|---|
| `doc.*`, `md.*`, `privacy.*`, `agents.md-length` | `ghagent doc --root .` | `tools/ghalib/mdcheck.py` |
| `repo.*`, `readme.*`, `changelog.*`, `agents.*`, `audit.*` | `ghagent audit .` | `tools/ghalib/audit.py` |
| `changelog.*` | `ghagent changelog check` | `tools/ghalib/changelog.py` |
| `assets.*` | `ghagent assets check` | `tools/ghalib/assets.py` |
| `wiki.*` | `ghagent wiki build`, `ghagent wiki verify` | `tools/ghalib/wiki.py` |
| `meta.*` | `ghagent meta check`, `ghagent meta apply`, `ghagent audit --repo` | `tools/ghalib/meta.py` |
| `install.*`, `verify.*`, `uninstall.*` | `ghagent install`, `verify-install`, `uninstall` | `tools/ghalib/install.py` |

Levels: `error` fails the command (exit `1`), `warn` is reported but does not change the exit
code, `info` is a note. `ghagent doc` accepts `--ignore <ids>`; `.ghagent.json` accepts the same
list as `ignore_rules`, and `audit` applies that list to its embedded document check.

## Configuration (`.ghagent.json`)

| Key | Effect |
|---|---|
| `owner_repo` | the default `<owner>/<name>` for `meta`, `changelog` and `wiki init` |
| `readme`, `agents`, `changelog`, `docs_dir`, `wiki_dir`, `wiki_manifest`, `ci_workflow` | where the files live; an absent file sets no trap |
| `require_files` | files this repository insists on; each missing one is a `repo.required-file` error |
| `ignore_rules` | rule ids switched off for the whole pack — `doc`, `audit` and `privacy` all honour it |
| `exclude_dirs` | extra directories the documentation walk must not enter (`site`, `_site`, `public`) |
| `safe_email_domains` | role domains of this repository; the built-in list holds only RFC examples and GitHub noreply addresses |
| `topic_min`, `topic_max`, `description_max` | metadata thresholds |
| `changelog_style`, `language` | the contract variant and the language of the localised copies |

Nothing in this file names a person: a repository that wants its own domain recognised adds it
here, and no project inherits somebody else's whitelist.

## Text hygiene

| Rule id | Level | What it checks |
|---|---|---|
| `doc.utf8` | error | the file is valid UTF-8; a decoding failure is a finding, not a crash |
| `doc.unreadable` | error | the file can be read at all |
| `doc.bom` | error | the file does not start with a UTF-8 BOM |
| `doc.crlf` | error | the file uses LF, not CRLF |
| `doc.final-newline` | warn | the file ends with a newline |
| `doc.tab-indent` | warn | indentation uses spaces; a tab-indented block is reported |
| `doc.line-length` | info | a prose line is longer than 200 characters (tables and URLs are exempt) |
| `md.hard-break` | warn | a trailing double space (markdown hard break) — use a blank line instead |
| `doc.no-text-files` | error | the tree contains at least one text file; an empty tree is not success |
| `coverage.skipped` | info | a rule examined nothing on this tree and says so |

House style wraps prose near 100 characters; the automated limit is deliberately looser, because
a hard limit invites unnaturally short lines rather than readable ones.

## Markdown structure

| Rule id | Level | What it checks |
|---|---|---|
| `md.h1` | error | exactly one `H1`; a template (`.github/`, a `template` filename, or the `<!-- ghagent: template -->` marker) and a wiki partial (`_Sidebar.md`, `_Footer.md`, `_Header.md`) may start at `H2` and are reported as info |
| `md.heading-skip` | warn | no heading level is skipped (`H2` → `H4`) |
| `md.fence` | error | every code fence is closed; a fence without a language tag is a warning |
| `md.table` | error | a table's separator and every row have as many cells as its header |
| `md.toc` | error | a listed TOC anchor is produced by a heading; an `H2` missing from an existing TOC is a warning |
| `md.alert` | warn | a `> [!TYPE]` alert uses one of `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION` |

## Links and anchors

| Rule id | Level | What it checks |
|---|---|---|
| `md.link-local` | error | a relative link target exists in the tree; inside a wiki checkout a page name resolves to `Page.md` (see below) |
| `md.link-anchor` | error | an anchor exists in the target file or the current document, compared case-insensitively |
| `md.link-dir` | warn | a link points to a directory instead of a file (info when it ends with a slash) |
| `md.image-alt` | warn | every image has non-empty alt text |
| `md.image-http` | warn | an image is not loaded over plain `http://` (mixed content is blocked) |

Anchors follow GitHub: the heading is lowercased, punctuation is dropped, spaces become hyphens,
an em dash disappears and leaves a double hyphen, duplicates gain `-1`, `-2`. Cyrillic headings
work; `#Установка` is written exactly as GitHub renders it.

### Wiki mode is detected, never assumed

A GitHub wiki links its own pages by name: `[Architecture](Architecture)` is `Architecture.md`.
The same link in an ordinary repository is a 404, so the resolution cannot be a default. The
checker switches it on per directory: the presence of `_Sidebar.md` or `_Footer.md` proves a wiki
checkout, and the configured `wiki_dir` (`wiki/` by default) proves wiki sources, whose sidebar is
generated only at build time. There `Page`, `Page#anchor` and names with dots
(`Migration-3.x-to-4.0`) resolve.
Everywhere else the link stays an error. `_Sidebar.md`, `_Footer.md` and `_Header.md` are also
exempt from `md.h1`: the wiki renders them as navigation on every page, not as documents.

> **Why this matters.** On a 24-page wiki the checker reported 121 errors, 119 of them on correct
> links. The only way to keep the gate green was `--ignore md.link-local,md.h1`, which also
> switched off the two rules that find real breakage.

## Privacy

| Rule id | Level | What it checks |
|---|---|---|
| `privacy.secret` | error | GitHub tokens (`ghp_`, `github_pat_`), AWS keys (`AKIA…`), private key blocks, Slack tokens, literal bearer values |
| `privacy.abs-path` | error | absolute machine paths: a drive letter with a `Users` directory, or a Unix home directory |
| `privacy.email` | warn | a personal e-mail address; `users.noreply.github.com`, `example.com`, `example.org`, `example.net` and `localhost` are allowed, and a repository adds its own role domains with `safe_email_domains` |

Placeholders instead of values: `<token>`, `<owner>/<repo>`, `example.com`,
`user@users.noreply.github.com`, `<path>`. The privacy scan runs inside `doc` on every file it
examines, and `ghagent privacy` runs it over the whole tree without the documentation rules.

### What the walk does not enter

`doc` and `privacy` use one walker, so they cannot disagree about the same tree. It skips build
output (`node_modules`, `vendor`, `dist`, `build`, `target`, …) and every directory whose name
starts with a dot — that is tool state: `.git`, `.idea`, `.ruff_cache`, and the scratch space of a
coding agent (`.swarm`, `.claude`, `.dsh`, `.cursor`). Two dot-directories are published surfaces
and stay: `.github/` and `.well-known/`. A project adds its own build directory with `exclude_dirs`
in `.ghagent.json` instead of teaching the pack the name of its generator.

The reason is measured: six `privacy.abs-path` errors came from plan files in an agent scratch
directory — machine paths that are never published, reported against a repository that was clean.

## AGENTS contract

`AGENTS.md` at the repository root is the entry point an agent reads first. The audit checks it
for the four properties that make it usable, and the document checker caps its length.

| Check | Level | Requirement |
|---|---|---|
| `agents.present` | pass | `AGENTS.md` exists at the root of the examined tree (the item is created only when the file was found; an absent file is `repo.agents`) |
| `agents.commands` | warn | contains copy-paste commands (a code fence or inline code) |
| `agents.verify` | warn | contains an explicit verification step |
| `agents.traps` | warn | contains explicit prohibitions ("do not", "trap") |
| `agents.md-length` | warn | the file is at most 120 lines; above that it stops being a map |

Structure the checks expect: one `H1`, a purpose paragraph, a TOC, a command table, the
non-negotiable rules, a verification block, a "do not" list and links to the detailed documents.
`agents.md-length` counts `len(text.splitlines())`, so a final newline is not an extra line, and
it looks only at the root `AGENTS.md` — not at `AGENTS.ru.md`, not at a nested copy.
The reason for the cap is cost: an agent pays for every token of this file on every request.
Detail belongs in this file, [WIKI.md](WIKI.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

## README contract

| Check | Level | Requirement |
|---|---|---|
| `readme.h1` | error | exactly one `H1`, kept under 60 characters (a longer title is a warning) |
| `readme.summary` | error | one prose paragraph directly after the title: what it is, for whom |
| `readme.badges` | error/warn | 3–8 badges; fewer than three is a warning, none is an error |
| `readme.toc` | warn | a table of contents is present; the contract wants it once the file passes roughly 200 lines |
| `readme.install` | error | an installation section (`Installation`, `Install`, `Установка`, `Getting started`, …) |
| `readme.usage` | error | a usage section (`Usage`, `Quick start`, `Быстрый старт`, `Examples`, …) |
| `readme.license` | error | a licence section |
| `readme.code-fence` | warn | every code fence has a language tag |
| `readme.absolute-link` | info | an absolute link to a `.md` file; a relative link renders in the tree and in the wiki mirror |
| `readme.emoji`, `readme.superlative` | warn | no emoji or unverifiable superlative in the summary line |

Two conventions a reviewer enforces because they cannot be computed: every table of numbers
names the measurement source in a column, and the summary states a capability a reader can check.
"Fast" and "powerful" are not measurements; a self-test count without the command that produced
it is a claim, not a number.

## Audit items

`ghagent audit` scores weighted items instead of printing a single verdict. A required file
contributes `repo.<name>` at its severity: `readme`, `license`, `changelog`, `contributing`,
`security` are errors; `code-of-conduct`, `support`, `agents`, `gitattributes`, `editorconfig`,
`gitignore`, `pr-template`, `issue-forms`, `ci`, `codeowners`, `dependabot` are warnings;
`citation` is info. Files demanded by `require_files` in `.ghagent.json` are `repo.required-file`
(errors).

The score counts a pass at full weight, a warn at half, a fail at zero, and excludes skipped items
from both sides; `audit.score` warns below 80% and errors below 60%, and `audit.no-items` errors
when nothing was examined at all. The other audit items are named in their contract sections:
`readme.*`, `changelog.*`, `agents.*`, plus `assets.banner`, `assets.social-preview` and
`wiki-source`. `wiki-source` is **skipped**, not failed, when the tree has no `wiki/` directory: a
repository may keep its wiki in its own git repository, which is what GitHub does by default, and
neither choice is a defect.

## CHANGELOG contract

Keep a Changelog 2.0.0 with semantic versions, ISO dates, newest first, `[Unreleased]` on top and
comparison links at the bottom. Six change types are recognised in English and Russian:
`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security` (`Добавлено`, `Изменено`,
`Устарело`, `Удалено`, `Исправлено`, `Безопасность`).

```markdown
# Changelog

All notable changes to this project are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/) 2.0.0, and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-10-30

### Added

- Something a user can see.

[Unreleased]: https://github.com/owner/repo/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/owner/repo/compare/v1.1.0...v1.2.0
```

| Rule id | Level | What it checks |
|---|---|---|
| `changelog.missing` | error | the file exists |
| `changelog.h1`, `changelog.h1-position` | error, warn | one `H1`, on line 1 |
| `changelog.format-link`, `changelog.semver-link` | warn | the preamble names Keep a Changelog and Semantic Versioning |
| `changelog.versions` | error | at least one `## [x.y.z] - YYYY-MM-DD` section |
| `changelog.unreleased` | warn | an `[Unreleased]` section exists |
| `changelog.duplicate` | error | a version appears once |
| `changelog.date-missing`, `changelog.date-format`, `changelog.date-future` | error, error, warn | every released version has an ISO date, and not in the future |
| `changelog.order` | error | versions are ordered newest first, by date and by SemVer |
| `changelog.empty-version` | error | a version has no content at all |
| `changelog.prose-version` | warn | a version is described in prose, with no `###` subsections (`empty-version` when there is nothing at all) |
| `changelog.types`, `changelog.type-order` | warn | known change types, in the canonical order; a grouping subtitle is dropped before the lookup (`### Added — template language` is `Added`) |
| `changelog.link-refs` | warn | `[x.y.z]` headings without link references at the bottom; the references are optional in Keep a Changelog, so the finding is a warning |
| `changelog.version`, `changelog.write`, `changelog.post-check` | error | `release` refuses an invalid version, an unverifiable rewrite, or a changelog that fails its own check after writing |
| `changelog.dry-run` | info | `release` without `--write` shows what would change |
| `changelog.suggest`, `changelog.suggest-empty`, `git.log` | info, warn, error | `suggest` drafts entries from conventional commits; a human writes the entry |

`changelog release 1.2.0 --write` promotes `[Unreleased]`, inserts the dated heading and rewrites
the comparison links; it verifies the result before and after writing. `changelog notes 1.2.0`
prints the release body, link references stripped. The template is
[reference/changelog-template.md](../reference/changelog-template.md).

## Wiki contract

The wiki is a separate repository with a flat namespace; the full workflow is in
[WIKI.md](WIKI.md). The rules that decide whether a build is publishable:

| Rule id | Level | What it checks |
|---|---|---|
| `wiki.source` | error | `wiki/` exists |
| `wiki.manifest` | error in `build`, warn in `audit` | `wiki/wiki.json` exists |
| `wiki.page-missing`, `wiki.page-unlisted` | error | manifest and disk list the same pages; an unlisted page is invisible |
| `wiki.home` | error | `Home.md` exists |
| `wiki.image-relative` | error | every image is absolute; the wiki cannot see the project tree |
| `wiki.link-broken`, `wiki.link-outside` | error | a `.md` link resolves to an existing page or repository file, inside the repository |
| `wiki.md-suffix` | error | an internal wiki link carries no `.md` |
| `wiki.link-target` | error | a link points at a page in the built tree |
| `wiki.required` | error | `Home.md`, `_Sidebar.md`, `_Footer.md` are in the built tree |
| `wiki.page-orphan` | warn | a page is reachable from the sidebar |
| `wiki.sidebar-target` | error | every sidebar link resolves |
| `wiki.footer-relative` | warn | the footer uses absolute links only |
| `wiki.remote-missing` | error | the wiki remote exists; GitHub creates it on the first page saved in the web interface |
| `wiki.build-missing` | error | `verify` found sources but no build: run `wiki build` (or `wiki publish --push`, which builds first) |
| `wiki.not-applicable` | info | neither sources nor a build: nothing to verify, exit `0` — a wiki kept in its own repository is checked in that checkout |
| `wiki.kept`, `wiki.dry-run`, `wiki.no-change` | info | publication is a dry run without `--push`; unmatched remote pages are kept unless `--prune` |

`wiki verify` resolves its target in a fixed order: an explicit `--out`, then a `--wiki-dir` that
already looks like a wiki (`Home.md`, `_Sidebar.md` or `_Footer.md` present), then the build under
`.ghagent/wiki`. The header of the report names the directory that was actually read, so
`--root <repo> --wiki-dir <clone>` verifies the clone and says so.

Manifest sample (the only ordering authority):

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

Copyable starting points: [reference/wiki-manifest-template.json](../reference/wiki-manifest-template.json)
and [reference/wiki-home-template.md](../reference/wiki-home-template.md).

## Images and assets

| Rule id | Level | What it checks |
|---|---|---|
| `assets.no-readme` | error | `README.md` exists, so a reference can be examined |
| `assets.readme-banner` | error | the README references at least one image |
| `assets.missing-file` | error | a referenced image is committed |
| `assets.alt` | warn | every image has alt text |
| `assets.insecure-url` | warn | an image is not loaded over plain `http://` |
| `assets.social-preview` | warn | a file named `social-preview.*` exists under `assets/` |
| `assets.social-size` | error | the preview is at most 1 MB |
| `assets.social-dimensions` | error/warn | the preview is at least 640×320; 1280×640 is the recommended size (reported as info) |
| `assets.svg-social` | warn | the preview is a PNG, JPG or GIF; an SVG renders in a README but is rejected as a social preview |
| `assets.no-pillow` | warn | `assets render` produced the SVG but no PNG |
| `assets.truncated` | warn | the eyebrow, title, summary, tagline or a terminal line does not fit the card and was cut |
| `assets.facts-overflow` | warn | more pills were requested than the card can show; the finding names the dropped ones |
| `assets.terminal-overflow` | warn | the terminal panel has room for a few lines; the finding says how many are hidden |
| `assets.derived-command` | info | the terminal command comes from a manifest's console script, not from `--command` |
| `assets.no-command` | info | the card has no terminal panel: neither a command nor output was given |
| `assets.dry-run`, `assets.written` | info | `render` without `--write` writes nothing |
| `assets.upload-hint` | info | the repository copy is not the social preview until it is uploaded in Settings → Social preview |

### The card

`assets render` draws one 1280×640 card: a dark vertical gradient, an accent top rule, an eyebrow, a
monospace wordmark whose first letter carries the accent colour, a bold summary, a muted tagline, a
row of fact pills, a terminal panel with traffic lights and command output, and a footer with the
repository URL on the left and the homepage behind a green status dot on the right. One layout
description (`BannerSpec` → `Card`) feeds both renderers, so the PNG and the SVG carry the same
coordinates: the SVG is a faithful twin, not a second design.

A multi-word wordmark is laid out word by word with one designed gap (0.35 em) rather than the
monospace space cell, which reads as a double space at display size; both renderers read that one
layout, so a word gap cannot be counted twice. A card with neither a command nor output lines draws
no terminal panel at all — the identity block is centred instead, because an empty terminal box
looks unfinished.

| Flag | Meaning |
|---|---|
| `--title` | the wordmark; defaults to the README `H1` |
| `--eyebrow` | the small accent line above it |
| `--summary` | the bold statement; defaults to the first README paragraph |
| `--tagline` | the muted line; defaults to the manifest description |
| `--command` | the command in the terminal panel; defaults to the manifest console script with `--help` |
| `--output`, `--output-line` | terminal output lines; nothing else is drawn, so no output is invented |
| `--fact LABEL=VALUE` | a fact pill, drawn value-first (`"MCP tools=40"` becomes `40 MCP tools`); repeatable, at most six |
| `--facts auto` / `--facts none` | `auto` (the default without `--fact`) derives measurable facts; `none` disables derivation |
| `--license` | SPDX id for the license pill; defaults to what the tree declares |
| `--footer-left`, `--footer-right` | footer text overrides |
| `--url`, `--homepage` | the repository URL and the homepage that gets the status dot |
| `--accent` | accent colour as `#rrggbb` |
| `--chips` | text-only pills; kept for older callers |
| `--size`, `--out-dir`, `--write` | canvas, output directory, and actually writing the files |

### Facts are measured, never guessed

`--facts auto` draws a pill only when the tree proves it, and `--json` names the source of every pill
it drew:

| Fact | Source |
|---|---|
| version | `[project].version`, the `[tool.hatch.version]` path and pattern, `package.json`, `CITATION.cff`, `VERSION`, a local tag |
| license | the manifest license, else the SPDX line or the first lines of `LICENSE` |
| runtime dependencies | the declared dependency array of `pyproject.toml` or `package.json` |
| tests | `def test_…` functions under `tests/` |
| wiki pages | the entries of the wiki manifest, else `wiki/*.md` |
| documentation pages | `docs/**/*.md`, translations excluded |
| languages, source files | the extensions present in the tree |

A missing manifest, license, test suite or wiki means that pill is absent, not estimated. Explicit
`--fact` values come first; auto facts fill the remaining slots. Emoji from a `README` H1 are
stripped — the font set has no colour glyphs, so they land as a box.

`python tools/make_social_preview.py --write` renders this repository's own card through the same
renderer, with an eyebrow, a summary, a homepage footer and a terminal panel whose lines are the
output of three gate commands executed seconds earlier — which is the only reason the picture can be
trusted.

## Metadata

| Rule id | Level | What it checks |
|---|---|---|
| `meta.empty` | error | the description is not empty |
| `meta.hard-limit`, `meta.length` | error, warn | the description fits the API limit of 350 characters and reads well under 200 |
| `meta.prefix` | warn | the description does not start with "a tool", "a simple", "this is", "the repo", "tool for" |
| `meta.superlative`, `meta.emoji`, `meta.shape` | warn/warn/info | no unverifiable superlative, no emoji, at least one clause |
| `meta.topics-count` | warn/error | 8–20 topics; more than 20 is an error because the API stores 20 |
| `meta.topics-form` | error | topics are lowercase and hyphenated (`[a-z0-9]+(-[a-z0-9]+)*`) |
| `meta.topic-year`, `meta.topic-duplicate` | warn | no year suffix, no duplicates |
| `meta.topics-put`, `meta.verify`, `meta.patch`, `meta.refused` | error (warn when only the stored topic list differs) | a write lands and reads back; validation errors block a write |
| `meta.remote` | error | `meta check --repo owner/name` could not read the repository through `gh api`; an unread remote is reported as such, never as an empty description |
| `meta.dry-run`, `meta.no-change` | info | `apply` without `--write` changes nothing |
| `meta.description`, `meta.description-length`, `meta.description-form`, `meta.homepage`, `meta.license`, `meta.releases`, `meta.community-health`, `wiki.enabled` | audit item levels | remote metadata read through `gh api` in `audit --repo` |

`PUT /repos/{owner}/{repo}/topics` replaces the whole list, so `meta apply` merges with the
existing set unless `--replace-topics` is given, then re-reads the response instead of trusting
the call.

## Install contract

`install` copies the pack into an agent skill root and writes `.install.json` with a sha256 per
file; `verify-install` answers the only question that matters later: is this the copy that passed
the tests.

| Rule id | Level | What it checks |
|---|---|---|
| `install.source`, `install.empty` | error | the source is a pack checkout and contains files to copy |
| `install.dry-run`, `install.done` | info | without `--write` nothing is copied; afterwards the report counts the files |
| `verify.manifest`, `verify.empty` | error | the directory carries an install manifest listing files |
| `verify.missing`, `verify.changed` | error | every installed file is present and unchanged |
| `verify.extra`, `verify.ok` | info | a file outside the manifest; a clean comparison |
| `uninstall.refused` | error | removal refuses a directory that this pack did not install |

Import paths and profiles are in [IMPORT.md](IMPORT.md); the wheel carries the CLI only, so
`install`, `verify-install`, `uninstall`, `snippet` and `selftest` are source-tree commands.

## Platform traps

Rows are ordered by the symptom a reader hits first. Full platform context is in
[WIKI.md](WIKI.md) and [PROCEDURES.md](PROCEDURES.md).

| Symptom | Trap | Action |
|---|---|---|
| `remote: Repository not found` on a wiki push | the wiki repository is not created by a push | save the first page in the web interface, then publish |
| a page exists but wiki search never shows it | wikis are barely indexed | only wikis with 500+ stars and public editing disabled are indexed; use GitHub Pages for discovery |
| no wiki on a private repository | a private wiki needs a paid plan | do not promise it |
| a link to `docs/page` fails | the wiki is a flat namespace | every page is a filename in the wiki root |
| an image does not render in the wiki | a relative image cannot work across repositories | commit it to the project and use an absolute raw URL |
| a wiki link opens a raw file or a 404 | `.md` in a wiki link | drop the extension |
| `#Установка` is not found | Cyrillic anchors | lower case, punctuation dropped, spaces become hyphens |
| a heading anchor has a double hyphen | an em dash in a heading | the dash is removed; two spaces become two hyphens |
| topics you did not touch disappear | `PUT /topics` replaces the list | merge with the existing set, then re-read |
| some topics vanish after a write | more than 20 topics | the API stores 20 |
| `422 Your current plan does not support GitHub Pages` | Pages for a private repository | the free plan does not allow it |
| 404 right after enabling Pages | Pages builds are asynchronous | poll the build, then the URL |
| base64 with line breaks in `gh api --jq .content` | the contents API returns encoded content | `-H 'Accept: application/vnd.github.raw'` |
| the social preview is rejected or blank | an SVG as a social preview | PNG, JPG or GIF only |
| an anchor that "should" be lowercase is not | the platform's own example contradicts the capital-Greek rule | compare anchors case-insensitively |

## Non-negotiable rules and their reasons

The nine rules in [AGENTS.md](../AGENTS.md) are not style preferences; each one has a failure it
prevents.

| Rule | Why it exists | Enforced by |
|---|---|---|
| Only measured numbers | one unverifiable figure discredits every other figure in the document | review; `readme.superlative`, `readme.emoji`, `meta.*` |
| No secrets, machine paths or personal addresses | published history is permanent, and a leaked token has to be rotated | `privacy.secret`, `privacy.abs-path`, `privacy.email` |
| One H1, a language tag on every fence | parsers, search snippets and syntax highlighting depend on it | `md.h1`, `md.fence`, `readme.code-fence` |
| Flat wiki namespace, absolute images, sidebar and footer | the wiki is a separate repository with no directories and no access to the project tree | `wiki.md-suffix`, `wiki.image-relative`, `wiki.required` |
| Publication only on an explicit flag | a pushed wiki page is public at once and cannot be recalled | `wiki.dry-run`, `wiki.kept`, `--prune` without a default |
| Keep a Changelog 2.0.0 | users and release tooling read the changelog, not the commit log | `changelog.*` |
| AGENTS.md under 120 lines | an agent pays for every line on every request; detail is fetched only when needed | `agents.md-length` |
| A false PASS is worse than a false FAIL | a green check that examined nothing hides the defect it was hired to find | `coverage.skipped`, `audit.no-items` |
| English canonical, owner-signed commits | one canonical text prevents silent drift; an agent signature misattributes responsibility | review; translation parity |

## House rules a reviewer enforces

- English is canonical; `NAME.ru.md` mirrors `NAME.md` in the same commit. A lagging translation
  is a defect, not a backlog item.
- One logical change per pull request, conventional commit subject, motivation in the body.
- Commits are signed by the repository owner, never by the agent or a bot identity.
- No runtime dependencies; Pillow stays an optional extra and only affects PNG output.
- Documentation changes with the code: a changed flag, exit code or rule id updates this file and
  [AGENTS.md](../AGENTS.md) in the same change.
- A rule without a failing fixture and a decoy is rejected; see
  [ARCHITECTURE.md](ARCHITECTURE.md#test-doctrine) and [../CONTRIBUTING.md](../CONTRIBUTING.md).
