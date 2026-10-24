---
name: changelog-release
description: Changelog and version releases by Keep a Changelog 2.0.0 and Semantic Versioning — conformance check, promoting Unreleased into a dated version with comparison links, a draft from conventional commits, and a release body for gh release. Load when preparing a release, when a changelog does not say what changed, when versions are out of order or dates are missing.
---

# Changelog and release

## The contract (Keep a Changelog 2.0.0)

- Six types and only them: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.
  The type answers "what is this", the text answers "why it matters".
- Version: `## [1.2.3] - 2026-10-24`. The date is ISO, otherwise versions cannot be sorted or
  linked.
- `## [Unreleased]` on top; on release its content moves into a new version.
- Newer versions above older ones.
- Comparison links at the bottom; `Unreleased` compares against the last tag:

```markdown
[Unreleased]: https://github.com/owner/repo/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/owner/repo/compare/v1.0.0...v1.1.0
```

- A breaking change is marked `**Breaking:**` inside its entry, not as a separate section.
- An entry addresses a user, not a commit: "the expiry countdown no longer loses a day", not
  "fix off-by-one in ExpiryCalculator".

## Commands

```bash
python <pack>/tools/ghagent.py changelog check
python <pack>/tools/ghagent.py changelog suggest --since v1.1.0
python <pack>/tools/ghagent.py changelog release 1.2.0 --write
python <pack>/tools/ghagent.py changelog check                 # after writing
python <pack>/tools/ghagent.py changelog notes 1.2.0 > release-body.md
gh release create v1.2.0 --notes-file release-body.md --title v1.2.0
```

Exit codes: `0` clean, `1` format errors, `2` no file or a non-SemVer version.

## What `check` verifies

| Rule | Example of a violation |
|---|---|
| `changelog.date-missing` | `## [1.1.0]` with no date |
| `changelog.date-format` | `## [1.1.0] - 20.10.2026` |
| `changelog.order` | version 1.0.0 above 1.1.0 |
| `changelog.duplicate` | two entries for the same version |
| `changelog.empty-version` | a version heading with no entries |
| `changelog.types` | a section called "Misc" instead of `Changed` |
| `changelog.link-refs` | `[1.1.0]` references with no definitions at the bottom |
| `changelog.unreleased` | no `[Unreleased]` section (warning) |

## Release order

1. `check` — the changelog is in order before the release.
2. `suggest --since <tag>` — a draft from commits. It is a **draft**: an entry tells a user what
   changed, it does not retell the log.
3. Finish the draft by hand under `[Unreleased]`.
4. `release <version> --write` — moves the section, sets the date, updates comparison links and
   re-checks the file immediately. If errors appear after the write, they are printed: a
   half-released changelog never passes silently.
5. `notes <version>` — the release body without service links.
6. Tag `vX.Y.Z`, signed by the owner.

## Choosing the number

| Change | Version |
|---|---|
| a fix, nothing added | patch `1.2.3 → 1.2.4` |
| a new capability, compatible | minor `1.2.3 → 1.3.0` |
| a breaking change in behaviour or API | major `1.2.3 → 2.0.0` |
| before `1.0.0` | `0.y.z`: a minor may break, and that must be stated |

## Traps

| Trap | Symptom | Action |
|---|---|---|
| A changelog made from the commit log | entries like `fix: typo`, `Merge pull request #12` | write entries again, in human words |
| Mixed heading languages in one file | half the entries are not found | pick one language; the tool accepts both sets, not a mix |
| A date in the future | a version "released tomorrow" | `changelog.date-future` warns |
| A version with no sections | an empty version in history | `changelog.empty-version` |
| A forgotten comparison link | `[1.2.0]` does not open | `release` adds it |

## Done means

- `changelog check` exits `0`.
- Every entry explains the change to a user and does not retell a commit.
- `notes` produces text that can be sent as is.
