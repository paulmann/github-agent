# Release

A release is not just a tag. It is a changelog entry, a date, comparison links and a release
body — and they must agree with each other.

## Order

```bash
python tools/ghagent.py changelog check
python tools/ghagent.py changelog suggest --since v1.1.0
python tools/ghagent.py changelog release 1.2.0 --write
python tools/ghagent.py changelog check
python tools/ghagent.py changelog notes 1.2.0 > release-body.md
gh release create v1.2.0 --notes-file release-body.md --title v1.2.0
```

## What `release` does

| Step | Result |
|---|---|
| Validates the version | refuses a non-SemVer version or one that already exists |
| Validates `[Unreleased]` | refuses when there are no entries |
| Moves the sections | `[Unreleased]` is empty again, the new version carries the date |
| Updates the links | `[Unreleased]: …/compare/v1.2.0...HEAD`, `[1.2.0]: …/compare/v1.1.0...v1.2.0` |
| Re-checks the file | errors are printed immediately, not discovered a week later |

Without `--write` the command only shows what would change.

## Choosing the number

| Change | Number |
|---|---|
| a fix | patch `1.2.3 → 1.2.4` |
| a new capability, compatible | minor `1.2.3 → 1.3.0` |
| a breaking change | major `1.2.3 → 2.0.0` |
| before `1.0.0` | `0.y.z`: a minor may break, and that is stated explicitly |

## How to write an entry

| Poor | Good |
|---|---|
| `fix: off-by-one in ExpiryCalculator` | "the days-to-payment counter no longer loses a day" |
| `refactor` | "synchronisation runs as one request instead of three" |
| "various improvements" | three separate entries with an observable effect |
| "breaking change" as its own section | `**Breaking:**` inside the entry, in its type section |

An entry addresses a user: they should understand what changed in their work without reading the
code.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| A changelog built from the commit log | entries like `Merge pull request #12` | rewrite them in human words |
| A version without a date | `## [1.2.0]` | `release` sets the date |
| Two entries for one version | `changelog.duplicate` | merge them |
| A forgotten comparison link | `[1.2.0]` does not open | `release` adds it |
| A tag with no notes | an empty release | `changelog notes` produces the text |

## Done means

- `changelog check` exits `0`.
- `changelog notes` gives text that can be sent as is.
- The tag `vX.Y.Z` exists, signed by the owner, and the changelog entry matches it.

## Next

- [Platform traps](06-Traps).
- [Import into another agent](07-Import).
