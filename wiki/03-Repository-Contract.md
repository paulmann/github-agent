# File contracts

A check is possible only where a contract exists. Below is what the pack considers correct, and
how each part is verified.

## README.md

| Item | Rule | Rule id |
|---|---|---|
| Title | one `H1`, under 60 characters | `readme.h1` |
| Summary | a paragraph right after the title: what it is, for whom | `readme.summary` |
| Badges | 3–8: CI, release, license, runtime | `readme.badges` |
| Banner | an image above the first section, with alt text | `assets.readme-banner` |
| Table of contents | required once the file passes 200 lines | `readme.toc` |
| Installation | a section named `Installation` or `Установка` | `readme.install` |
| Usage | a section named `Usage` or `Быстрый старт` | `readme.usage` |
| License | a section named `License` or `Лицензия` | `readme.license` |
| Code | every fence carries a language | `readme.code-fence` |

## AGENTS.md

| Item | Why |
|---|---|
| Copy-paste commands | the agent must not guess the syntax |
| A verification section | how to prove the work is done |
| A prohibitions section | what not to do, and why |
| A map, not an encyclopedia | `agents.md-length` warns above 120 lines; detail belongs in `docs/` |
| A link to the traps table | the symptom that identifies each trap stays in the detailed document |

Since 1.2.0 the root `AGENTS.md` is a map under 120 lines: the rule catalogue, the file contracts
and the 15-row traps table live in
[docs/RULES.md](https://github.com/paulmann/github-agent/blob/main/docs/RULES.md), the wiki
workflow in [docs/WIKI.md](https://github.com/paulmann/github-agent/blob/main/docs/WIKI.md), and
the modules and exit codes in
[docs/ARCHITECTURE.md](https://github.com/paulmann/github-agent/blob/main/docs/ARCHITECTURE.md).

## CHANGELOG.md

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

Six types: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. Dates are ISO. Newer
versions sit above older ones. `Unreleased` stays on top.

## wiki/wiki.json

The manifest sets order and navigation. A file missing from the manifest is an error: the page
exists but cannot be found.

```json
{
  "repo": "owner/name",
  "branch": "main",
  "title": "Project name",
  "footer": "MIT",
  "groups": [
    {"title": "Start", "pages": ["Home.md", "01-Install.md"]},
    {"title": "Русский", "pages": ["Home.ru.md"], "labels": {"Home.ru.md": "Home (RU)"}}
  ]
}
```

## Images

| Rule | Rule id |
|---|---|
| The repository has an `assets/` directory with an image | `assets.no-directory` |
| The README references at least one image | `assets.readme-banner` |
| Every referenced file exists | `assets.missing-file` |
| The social preview is PNG/JPG/GIF | `assets.svg-social` |
| The social preview is under 1 MB | `assets.social-size` |
| The social preview is at least 640×320, ideally 1280×640 | `assets.social-dimensions` |
| No image over plain `http://` | `md.image-http` |

## What `doc` does

| Group | Rules |
|---|---|
| Text | `doc.bom`, `doc.crlf`, `doc.final-newline`, `doc.tab-indent` |
| Structure | `md.h1`, `md.heading-skip`, `md.fence` |
| Tables | `md.table` |
| Links | `md.link-local`, `md.link-anchor`, `md.link-dir` |
| Table of contents | `md.toc` |
| Markup | `md.alert`, `md.image-alt`, `md.image-http`, `md.hard-break` |
| Privacy | `privacy.secret`, `privacy.abs-path`, `privacy.email` |

A file carrying `<!-- ghagent: template -->` is exempt from link checks: a template contains
unresolved placeholders on purpose.

## The rule that matters most

If a rule examined zero objects it is **not** passed. The report names it in a `coverage.skipped`
line, and an empty tree produces `doc.no-text-files`. A check that checked nothing is more
dangerous than no check: it creates confidence.

## Next

- [Wiki workflow](04-Wiki-Workflow).
- [Platform traps](06-Traps).
