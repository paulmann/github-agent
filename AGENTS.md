# AGENTS.md — GitHub repository and wiki steward

Instructions for an agent that runs a GitHub repository and its wiki: audit hygiene, write README
and AGENTS.md, keep CHANGELOG and community files honest, render images, build and publish the
wiki, check links and anchors. Python 3.11+, standard library only; Pillow is optional and only
adds PNG output. This file is a map: detail is in the documents linked below.

## Contents

- [What the pack does](#what-the-pack-does) · [Install](#install) · [One command per job](#one-command-per-job) · [Non-negotiable rules](#non-negotiable-rules) · [Verification](#verification)
- [Where the detail lives](#where-the-detail-lives) · [Do not](#do-not) · [Pack layout](#pack-layout) · [License](#license)

## What the pack does

Most repositories fail on documentation, not code: no installation section, a CHANGELOG without
dates, a wiki of unlinked pages. Nothing fails, because `git push` succeeds and no check exists.
The pack turns each recurring job into one command: `0` clean, `1` with errors, `2` on bad usage.

## Install

```bash
uv tool install github-agent-cli            # recommended: isolated CLI
pipx install github-agent-cli               # alternative
pip install github-agent-cli                # Python 3.11+
pip install "github-agent-cli[png]"         # optional Pillow: PNG banner output only
ghagent --version                       # github-agent 1.2.2
```

The wheel ships the CLI only. The pack — `skills/`, `tools/`, `tests/`, `reference/`, `wiki/`,
`docs/` and the root documents — installs into an agent skill root from a clone; `selftest` and
`install` refuse in wheel mode. Profiles, `--target`, updating and removal:
[docs/IMPORT.md](docs/IMPORT.md).

```bash
git clone https://github.com/paulmann/github-agent.git
python tools/ghagent.py install --profile harness --write     # ~/.dsh/skills
python tools/ghagent.py install --profile autoclaw --write    # ~/.pi/agent/skills
```

## One command per job

| Job | Command | What it examines |
|---|---|---|
| Repository hygiene | `ghagent audit .` | required files, README and CHANGELOG contracts, score |
| Documents | `ghagent doc --root .` | BOM/CRLF, headings, tables, links, anchors, TOC, AGENTS length |
| Secrets and privacy | `ghagent privacy --root .` | tokens, machine paths, personal addresses |
| Images | `ghagent assets render\|check\|suggest` | banner, social preview, dimensions, references |
| Wiki | `ghagent wiki build\|verify\|publish` | manifest, sidebar, footer, link rewriting, publication |
| Changelog and release | `ghagent changelog check\|release\|suggest\|notes` | Keep a Changelog, release, notes |
| Metadata | `ghagent meta suggest\|apply` | description, topics, homepage |

All checks accept `--json` and print `file:line` plus a rule id; `report` combines them in one file.

## Non-negotiable rules

1. **Only measured numbers.** Every figure names its source: a command, a file, an API response.
2. **No secrets, machine paths or personal addresses** in the tree, examples included.
3. **One H1 per document and a language tag on every code fence.**
4. **The wiki is a flat namespace:** no `.md` in links, images by absolute URL, sidebar and footer.
5. **Publication only on an explicit flag.** `wiki publish` without `--push` is a dry run;
   `--prune` deletes remote pages and is a human decision.
6. **CHANGELOG follows Keep a Changelog 2.0.0:** ISO dates, newest first, comparison links.
7. **AGENTS.md is a map under 120 lines** (`agents.md-length` warns above that); detail is in `docs/`.
8. **A false PASS is worse than a false FAIL.** A rule that examined nothing reports
   `coverage.skipped`; empty success is a defect.
9. **English is canonical.** `NAME.ru.md` mirrors `NAME.md`; commits are signed by the owner.

## Verification

```bash
ghagent selftest          # clone only: tests/ is not in the wheel
ghagent doc --root .
ghagent audit .
ghagent changelog check
ghagent assets check
ghagent privacy --root .
```

All six must exit `0`. `1` means error-level findings printed with `file:line`; `2` means a wrong
path, a missing file, or a command that needs the source tree.

## Where the detail lives

| Document | Contains |
|---|---|
| [docs/RULES.md](docs/RULES.md) | full rule catalogue, file contracts, 15 platform traps, enforcement map |
| [docs/WIKI.md](docs/WIKI.md) | manifest, sidebar and footer, build/verify/publish, prune, first-page trap |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | modules, exit codes, report model, test doctrine, scope |
| [docs/PACKAGING.md](docs/PACKAGING.md) | PyPI, wheel and sdist, Action, Docker, pre-commit, build check |
| [docs/IMPORT.md](docs/IMPORT.md) | install into AutoClaw2, HARNESS and SagaAI; verify, update, remove |
| [docs/PROCEDURES.md](docs/PROCEDURES.md) | six recurring jobs with success and failure criteria |

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md); migration: [MIGRATION.md](MIGRATION.md); file
templates: [reference/](reference/).

## Do not

- Publish a wiki without `wiki verify` and without reading the dry run.
- Delete remote wiki pages for tidiness; `--prune` is a decision, not a habit.
- Rewrite the CHANGELOG from the commit log; `changelog suggest` drafts, a human writes.
- Add a runtime dependency, edit a `.ru.md` file alone, or leave the English original behind.
- Sign a commit as the agent, or claim a number the README does not contain.

## Pack layout

```text
AGENTS.md, AGENTS.ru.md   this map and its Russian mirror
README.md                 the project as a product; README.*.md translate it
docs/                     RULES, WIKI, ARCHITECTURE, PACKAGING, IMPORT, PROCEDURES
skills/, reference/       SKILL.md packs and file templates, each with .ru.md
tools/                    ghagent.py CLI and ghalib/ library modules
wiki/, tests/             wiki sources and manifest; fixtures, decoys, sandbox publication
packaging                 pyproject.toml, action.yml, Dockerfile, .pre-commit-hooks.yaml
```

## License

MIT — see [LICENSE](LICENSE).
