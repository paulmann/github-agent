# github-agent

A repository and wiki steward for GitHub: it scores the README, CHANGELOG and community
contracts, lints documents, links, anchors and tables, scans for leaked secrets, renders the
banner and social preview, and keeps the wiki in the repository — one command per job.

Python 3.11+, **no runtime dependencies**, exit codes `0` / `1` / `2`, and every finding is
`file:line` plus a rule id you can look up in [Rules](RULES.md).

```bash
ghagent audit . --min-score 85     # hygiene score, README and CHANGELOG contracts
ghagent doc --root .               # markdown, links, anchors, tables, privacy
ghagent changelog check            # Keep a Changelog 2.0.0 conformance
ghagent wiki build && ghagent wiki verify
```

## Why this exists

A repository rarely fails on code; it fails on documentation. The README has no installation
section, the changelog has no dates, the wiki is three pages without navigation, the banner is
a broken image, the description is one word. `git push` succeeds, so the defect lives for years.

The pack puts a verifiable contract on each of those places and reduces the work to one
command. It does not write marketing copy and does not invent numbers: it checks what a human
wrote and refuses to publish what is broken.

## Two ideas that shape every rule

- **A false `PASS` is worse than a false `FAIL`.** A rule that examined zero objects reports
  `coverage.skipped`; a check that could not run exits `2`, not `0`.
- **Every rule has a failing fixture, a decoy and a sentence here.** A rule that cannot be
  proven is removed, not shipped.

## Where to go next

| Page | What it answers |
|---|---|
| [Install](IMPORT.md) | package managers, the clone, agent skill roots, `verify-install` |
| [Rules](RULES.md) | the full rule catalogue: id, level, what it checks, which command produces it |
| [Architecture](ARCHITECTURE.md) | the modules and the data flow between them |
| [Wiki workflow](WIKI.md) | sources in the repository, built and published to the wiki namespace |
| [Packaging](PACKAGING.md) | PyPI, Homebrew, Scoop, Docker, the Action and the release procedure |
| [Procedures](PROCEDURES.md) | the exact sequences for a release, a wiki publish and a rescue |
| [Field notes](FIELD-NOTES.md) | what ten real repositories broke, and what changed because of it |

The repository root carries the files GitHub reads first: [`README.md`](../README.md),
[`AGENTS.md`](../AGENTS.md) (the protocol for an agent), [`CHANGELOG.md`](../CHANGELOG.md) and
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Licence

MIT. See [`LICENSE`](../LICENSE).
