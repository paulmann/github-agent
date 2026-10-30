# Changelog

All notable changes to this project are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/) 2.0.0, and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/paulmann/github-agent/compare/v1.2.2...HEAD
[1.2.2]: https://github.com/paulmann/github-agent/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/paulmann/github-agent/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/paulmann/github-agent/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/paulmann/github-agent/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/paulmann/github-agent/releases/tag/v1.0.0
