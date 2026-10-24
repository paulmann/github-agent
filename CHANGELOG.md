# Changelog

All notable changes to this project are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/) 2.0.0, and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/paulmann/github-agent/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/paulmann/github-agent/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/paulmann/github-agent/releases/tag/v1.0.0
