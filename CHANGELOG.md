# Changelog

All notable changes to this project are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/) 2.0.0, and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-11-02

### Added

- A designed social preview for `ghagent assets render`: a dark vertical gradient, an accent top
  rule, an eyebrow, a monospace wordmark whose first letter carries the accent colour, a bold
  summary and a muted tagline, a row of fact pills, a terminal panel with traffic lights and
  command output, and a footer with the repository URL on the left and the homepage behind a green
  status dot on the right.
- New `assets render` flags, each documented in `--help`: `--eyebrow`, `--summary`, `--fact`
  (`Label=Value`, repeatable), `--output` / `--output-line`, `--footer-left` / `--footer-right`,
  `--url`, `--homepage`, `--accent`, `--facts auto|none` and `--license`. `--title`, `--tagline`,
  `--command`, `--chips`, `--size`, `--out-dir` and `--write` keep working.
- `--facts auto` (the default when no `--fact` is given) derives only measurable pills: the version
  from the manifest (`[project]`, the `[tool.hatch.version]` path and pattern, `package.json`,
  `CITATION.cff`, `VERSION`, a local tag), an SPDX license from the manifest or `LICENSE`, the
  declared runtime dependency count, the test-function count in `tests/`, the wiki manifest
  entries, documentation pages, languages and source files by extension. A fact the tree cannot
  prove is omitted, and `--json` names the source of every pill it drew.
- `tools/make_social_preview.py`: this repository's own card, as a thin preset over the same
  renderer. It runs the three gate commands before drawing, so the terminal panel repeats what
  they printed seconds earlier.
- Self-tests for the card: the SVG carries every text instruction at the PNG coordinate, auto
  facts omit what cannot be measured, `--fact` overrides appear, the six-pill cap is reported,
  `--size` scales the layout, and every flag appears in `--help`.
- The generated `_Sidebar.md` / `_Footer.md` navigation is English — "### Links", "Repository",
  "Releases", "repository" — and a self-test holds it there.

### Changed

- `assets render` draws the designed card now; the flat card and the duplicated `render_svg` /
  `render_png` layout code are gone. Both renderers consume one `Card` instruction list, and the
  own card and the generic card share it, so the designs cannot drift apart.
- A card with neither a command nor output lines draws no terminal panel: the identity block is
  centred between the top rule and the footer instead of a large empty box, and `assets.no-command`
  says so.
- `assets/social-preview.png` and `assets/social-preview.svg` are regenerated (1280×640, 56 KB):
  the card shows 1.4.0, MIT, 0 runtime dependencies, 25 test functions, 16 wiki pages and 8
  documentation pages, every number measured from this tree.

### Fixed

- A multi-word wordmark was laid out with the monospace space cell, which reads as a double space
  at display size: the words are now placed by one layout with a 0.35 em gap, identical in the PNG
  and the SVG, and a self-test compares the word positions and the rendered ink gap.
- The generated wiki navigation carried Russian strings in an English project: `_Sidebar.md` said
  "Ссылки / Репозиторий / Релизы" and `_Footer.md` said "репозиторий / релизы".
- The pack hygiene test skipped build output and tool state: one `python -m build` wrote its own
  files under `dist/` and turned the gate red for a file nobody ships.

## [1.3.0] - 2026-11-01

### Added

- `docs/FIELD-NOTES.md`: ten defects that real repositories found, anonymised — the symptom, the
  cause, the rule that changed and the fixture that now holds it. Published as a page of the
  documentation site.
- A documentation site on GitHub Pages: `mkdocs.yml` (Material), `docs/index.md`,
  `.github/workflows/docs.yml` (build on every pull request, deploy from `main`) and
  `hooks/repo_links.py`, which points a link that leaves `docs/` at the repository instead of at a
  page that does not exist.
- `.github/workflows/codeql.yml` (CodeQL, security-and-quality queries) and a `lint` job in CI:
  `ruff` and `mypy` with their configuration in `pyproject.toml`. Both are development tools — the
  runtime dependency count stays zero.
- `.github/workflows/release-draft.yml`: a manual workflow that renders the release body from the
  CHANGELOG (`changelog notes`) and creates a **draft** release. A draft does not trigger
  `publish.yml`, so nothing reaches PyPI before a human presses Publish.
- `tools/make_demo.py` and `assets/demo.gif`: the README animation is rendered from the real
  output of three commands, so it cannot show anything the tool did not print.
- README sections **Why this exists** and **How it compares** (with `markdownlint`, `vale`,
  `action-gh-release`, pre-commit, `release-please` and the community-health files) in all six
  languages.
- `.ghagent.json` keys `exclude_dirs` (build output whose name the pack cannot know, e.g. `site`)
  and `safe_email_domains` (role domains of this repository).
- `packaging/homebrew/github-agent-cli.rb`: a Homebrew formula that installs the PyPI sdist
  `github_agent_cli-1.2.2.tar.gz` (sha256 `f60d17b1…e14ae`) into a virtualenv with `python@3.13`,
  with `livecheck` reading the PyPI JSON API. Canonical copy: `paulmann/homebrew-github-agent-cli`.
- `packaging/scoop/github-agent-cli.json`: a Scoop manifest for the Windows bundle
  `github-agent-cli-1.2.2-windows-x64.zip` (sha256 `2676f33b…c85a4`), `depends: python`,
  `checkver`/`autoupdate` from the PyPI JSON API and the release `SHA256SUMS.txt`. Canonical copy:
  `paulmann/scoop-github-agent-cli`.
- A Windows bundle in the release assets: `ghagent.cmd` plus the wheel contents under `lib/`. It was
  executed on Windows before upload (`--version`, `audit . --min-score 90`).
- CI job `manifests`: `ruby -c` for the formula, a real download of both URLs with the SHA-256
  compared against the manifest, and a layout check of the bundle. A wrong hash or a stale version
  fails the pull request.
- `packaging/README.md`: what each manifest installs, where the canonical copy lives and the bump
  procedure for both.

### Changed

- `md.link-local`: inside a wiki checkout — detected from `_Sidebar.md` or `_Footer.md` — a page
  name resolves to `Page.md`, including names with dots (`Migration-3.x-to-4.0`). In an ordinary
  repository the same link stays an error, because there it is a 404.
- `md.h1`: `_Sidebar.md`, `_Footer.md` and `_Header.md` are wiki furniture and are reported as a
  note, not as a document without a title.
- `doc` and `privacy` share one walker, which skips every dot-directory except `.github/` and
  `.well-known/`; `doc` also honours `ignore_rules` from `.ghagent.json`, which only `audit` read
  before.
- `changelog.link-refs`: missing link references are a warning, not an error — Keep a Changelog
  makes them optional. `changelog.types`: a grouping subtitle is dropped before the lookup, so
  `### Added — template language` is `Added`.
- `assets render`: chips come from the declared keywords (languages are the fallback), emoji are
  stripped from the title, and a title or tagline that would be cut is a warning that names the
  limit.
- `meta check --repo <slug>` reads the repository through `gh api` instead of validating the empty
  arguments it was given.
- `audit`: `wiki-source` is skipped, not failed, when the tree has no `wiki/` directory.
- `wiki verify`: the target is an explicit `--out`, then a `--wiki-dir` that already looks like a
  wiki checkout, then the build; the header names the directory that was read, and a repository
  with neither sources nor a build gets one note instead of an error.
- `docs/PACKAGING.md`: the Homebrew and Scoop section is no longer "deferred" — it lists both
  manifests, the measured hashes and how the CI job verifies them.
- The six READMEs and `AGENTS.md` gained the `brew` and `scoop` install commands.

## [1.2.2] - 2026-10-30

### Changed

- Publication is event-driven: publishing a GitHub release uploads that tag to PyPI
  (`release: types: [published]`). The manual `workflow_dispatch` path stays as an escape hatch and
  still requires the `publish` confirmation word. `skip-existing: true` makes a re-run of an
  already published version a no-op instead of a red job.
- `docs/PACKAGING.md` documents both authentication paths and the exact command sequence for a
  release, so the next release needs no repository archaeology.

## [1.2.1] - 2026-10-30

### Changed

- The PyPI distribution is **`github-agent-cli`**: `github-agent` (2.4.9, an unrelated MCP agent)
  and `ghagent` (0.0.1, a GitHub explorer) are already taken. The project, the console script
  `ghagent`, the library package `ghalib` and the `--version` output (`github-agent X.Y.Z`) keep
  their names; only the distribution name changes, so the installers are
  `uv tool install github-agent-cli`, `pipx install github-agent-cli`,
  `pip install github-agent-cli` and `pip install "github-agent-cli[png]"`. Every README,
  `AGENTS.md`, docs page, wiki page and example was updated, and the wheel and sdist are now
  `github_agent_cli-X.Y.Z-*`.
- `pyproject.toml` records why the distribution and the product names differ, and
  `docs/PACKAGING.md` explains the four names a user meets (distribution, console script,
  library package, repository) with the evidence for each.

### Fixed

- The six READMEs state that the package-manager commands resolve only after the first PyPI
  publication: Trusted Publishing is an owner step and the `Publish` workflow is manual. Until
  then the wheel from the latest release and the source clone are the paths that work, and they
  provide the same `ghagent` command.

## [1.2.0] - 2026-10-30

### Added

- PyPI package `github-agent` with the `ghagent` console script: `pip install github-agent`,
  `pipx install github-agent` or `uv tool install github-agent`, Python 3.11+ and no runtime
  dependency; the optional `[png]` extra adds Pillow for PNG banner output only.
- Reusable GitHub Action (`action.yml`), a composite action that installs this checkout and runs
  one `ghagent` command, by default `audit . --min-score 80`, with `python-version`,
  `working-directory` and `github-token` inputs.
- Docker image (`Dockerfile`): a two-stage build compiles the wheel from the source tree and
  installs it into `python:3.13-slim`; `ENTRYPOINT ["ghagent"]`, the audited repository at `/repo`.
- Pre-commit hooks (`.pre-commit-hooks.yaml`): `ghagent-doc`, `ghagent-audit`,
  `ghagent-privacy` and `ghagent-changelog`, built from the tagged revision with
  `language: python` and no separate installation step.
- `agents.md-length` rule: the canonical root `AGENTS.md` warns above 120 lines, with a hint to
  keep it a map and move detail into `docs/`. It counts the file it examined, and
  `--ignore agents.md-length` silences it; `AGENTS.ru.md` and a nested `docs/AGENTS.md` are not
  the canonical file and are not measured.
- Documentation split into `docs/RULES.md` (rule catalogue, file contracts, platform traps),
  `docs/WIKI.md`, `docs/ARCHITECTURE.md`, `docs/IMPORT.md`, `docs/PROCEDURES.md` and
  `docs/PACKAGING.md`; `AGENTS.md` is now a map under 120 lines that links to them.
- README restructure: the summary is the first paragraph after the H1, badges and the language
  switcher follow it, and installation, usage and verification are separate sections.

### Changed

- Heading anchors for non-Latin scripts: `slugify` keeps combining marks of every category
  (`Mn`, `Mc`, `Me`) instead of dropping the spacing marks, so a Devanagari heading and the
  table-of-contents link to it agree. Latin, Cyrillic and Greek anchors are unchanged.
- `audit` looks for the README summary past blank lines and HTML comments: an i18n switcher
  marker no longer fails `readme.summary`, while a comment-only README still does.
- Installed-package honesty: from a wheel `selftest` exits `2` and says the test suite ships only
  in the source tree, and `install`, `verify-install`, `uninstall` and `snippet` exit `2` and
  point at a git clone. No `PASS` is printed and no install manifest is written for a pack that
  is not there; from a clone the behaviour is unchanged.
- `PACK_VERSION` rises to 1.2.0, still single-sourced in `tools/ghalib/util.py` and read from
  there by `pyproject.toml`.
- CI runs the self-tests on Python 3.11 and 3.13, then documents and contracts, then builds the
  sdist and wheel and smoke-tests the installed console script in a clean virtual environment.

### Fixed

- A Windows console or redirected pipe that uses a non-UTF-8 code page (cp866, cp1251,
  cp1252) crashed on any non-Latin or non-ASCII finding, for example `ghagent assets check`
  printing its arrow hint: `UnicodeEncodeError: 'charmap' codec ...`. The CLI now reconfigures
  stdout and stderr to UTF-8 with `backslashreplace`, so the finding is printed and the exit
  code is unchanged; a stream that cannot be reconfigured is left alone.
- `README.hi.md` produced 17 `md.link-anchor` errors because the anchor computation dropped the
  Devanagari vowel signs; the Hindi table of contents now resolves and `ghagent doc --root .`
  exits `0` on this repository.
- A README whose H1 is followed by `<!-- md-i18n:switcher -->` failed `readme.summary`; the rule
  now skips the invisible comment and `ghagent audit .` scores this repository at 100% with no
  error.
- 39 new self-tests cover the non-Latin anchors, the comment-skipping summary, the new rule with
  its 150-line, 120-line and nested-file fixtures, the installed-wheel refusals, and the
  redirected-stream encoding; 173 checks in total.

## [1.1.0] - 2026-10-24

### Added

- `ghagent assets render|check|suggest` — the repository's own imagery: a 1280×640 social preview rendered from the project's metadata, a vector twin for the README, and a checker for format, byte size, dimensions, alt text and every referenced file. PNG output needs Pillow; without it the SVG is produced and the report says so instead of pretending a preview is ready.
- `skills/repo-images` — how to choose and place a banner, social preview, screenshot and diagram, with the platform limits that decide whether an image is usable at all.
- Bilingual documentation: English files are canonical, Russian translations carry the `.ru.md` suffix, including the wiki pages, which gain their own navigation group.
- 21 new self-tests for image rendering and checking, including decoys for a preview hidden in `node_modules` and for a file over the 1 MB limit.

### Changed

- `audit` now scores the README banner and the social preview, so a repository without a picture no longer passes as complete.
- The markdown checker warns about images loaded over plain `http://`.

### Fixed

- `wiki publish` reports `wiki.remote-missing` with the platform step instead of failing on a push that cannot create the wiki repository.
- Documentation counts refreshed: 134 self-tests, 13 commands, 11 library modules, 15 platform traps.

## [1.0.0] - 2026-10-24

### Added

- `ghagent audit` — required files, README contract, changelog contract and a hygiene score; a local tree or remote metadata through `gh api`.
- `ghagent doc` — UTF-8/BOM/CRLF hygiene, heading structure, tables, code fences, alerts, images, internal links and anchors, table-of-contents consistency, privacy rules.
- `ghagent wiki build|verify|publish|init` — manifest-driven wiki with `_Sidebar.md` and `_Footer.md`, link rewriting for the flat wiki namespace, dry-run publication that keeps remote pages it did not build.
- `ghagent changelog check|release|suggest|notes` — Keep a Changelog 2.0.0 conformance, promoting `[Unreleased]` with comparison links, a draft from conventional commits, and a release body.
- `ghagent meta suggest|apply` — description and topic validation, merged topic updates through `PUT /repos/{owner}/{repo}/topics`.
- `ghagent install|verify-install|uninstall|snippet` — installation into an agent skill root with a sha256 manifest, drift detection and a printed rules block.
- `ghagent report` — one markdown report combining hygiene, documents, changelog and wiki.
- 113 self-tests with fixtures for every rule, decoys for the rules that must stay quiet, and a sandbox publication against a local bare repository.
- Five skills: `github-repo`, `github-wiki`, `changelog-release`, `contributing-and-community`, `import-to-agents`.

### Security

- The pack ships without tokens, absolute machine paths or personal addresses; the privacy rule fails the build if one appears, and a self-test enforces it on the pack itself.

[Unreleased]: https://github.com/paulmann/github-agent/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/paulmann/github-agent/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/paulmann/github-agent/compare/v1.2.2...v1.3.0
[1.2.2]: https://github.com/paulmann/github-agent/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/paulmann/github-agent/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/paulmann/github-agent/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/paulmann/github-agent/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/paulmann/github-agent/releases/tag/v1.0.0
