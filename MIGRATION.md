# Migration from 1.1.0 to 1.2.0

This guide is for the owner of a repository that uses github-agent — either as a CLI, as a pack
installed into an agent skill root, or as a checking step in CI. It records what moved, what
changed meaning, and what needs an action. Version 1.2.0 does not break the 1.1.0 workflow: the
commands, flags, exit codes and file contracts are the same, so most repositories have nothing
to migrate.

## At a glance

| Area | 1.1.0 | 1.2.0 |
|---|---|---|
| Install | clone the repository, run `python tools/ghagent.py` | `uv tool install github-agent`, `pipx install github-agent` or `pip install github-agent`; console script `ghagent` |
| Source tree | the only way to run | unchanged: `python tools/ghagent.py <command>` still works and is what the pack's own docs use |
| Pack installation | `install --profile … --write` from a clone | unchanged, still from a clone; the wheel ships the CLI only and refuses `install`/`selftest` with exit `2` |
| Rule catalogue | inside a 296-line `AGENTS.md` | `AGENTS.md` is a map under 120 lines; the catalogue is [docs/RULES.md](docs/RULES.md) |
| Wiki workflow | split between `AGENTS.md` and `docs/PROCEDURES.md` | [docs/WIKI.md](docs/WIKI.md) |
| Modules, exit codes, tests | `AGENTS.md` | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Packaging and release | not documented | [docs/PACKAGING.md](docs/PACKAGING.md), `pyproject.toml`, `action.yml`, `Dockerfile`, `.pre-commit-hooks.yaml` |
| Long-form rules | `AGENTS.md` | [docs/RULES.md](docs/RULES.md); `docs/IMPORT.md` and `docs/PROCEDURES.md` stay and are linked from the map |
| AGENTS.md length | no limit | new rule `agents.md-length` warns above 120 lines |
| README | internals first | installation first; the badge block names the CI workflow, the supported Python range, the licence, the runtime dependency count and the self-test count |
| Version source | `tools/ghalib/util.py` | unchanged — `PACK_VERSION` in `tools/ghalib/util.py` is the only place the number lives |

## Step by step

### 1. Update the tool

CLI only:

```bash
uv tool install --upgrade github-agent     # or: pipx upgrade github-agent
pip install --upgrade github-agent         # pip into the active environment
ghagent --version                          # must print: github-agent 1.2.0
```

From a clone, for the pack:

```bash
git -C <checkout> pull
python tools/ghagent.py selftest            # must print PASS
```

The clone is not optional for the pack commands: `install`, `verify-install`, `uninstall`,
`snippet` and `selftest` copy or test files that a wheel does not contain, so in a wheel
installation they exit `2` with a message that names the missing tree. That is the intended
behaviour, not a broken install.

### 2. Refresh an installed pack

If the pack lives in an agent skill root, reinstall and verify it:

```bash
python tools/ghagent.py install --profile harness --write     # or --profile autoclaw
python tools/ghagent.py verify-install --profile harness
```

`install` overwrites the copied files and rewrites `.install.json`; the manifest now records
version `1.2.0`, so a stale copy is visible instead of silently trusted. Profile paths and
`--target` are unchanged — see [docs/IMPORT.md](docs/IMPORT.md).

### 3. Read the new map, not the old monolith

`AGENTS.md` now answers "what do I run and what must I not break" and links to the detail.
If you kept a local copy of the old `AGENTS.md` in your own rules, replace the copy; the rules
themselves did not change, they moved:

| You looked for | In 1.1.0 | In 1.2.0 |
|---|---|---|
| Rule ids and file contracts | `AGENTS.md` | [docs/RULES.md](docs/RULES.md) |
| Platform traps (15 rows) | `AGENTS.md` | [docs/RULES.md](docs/RULES.md#platform-traps) |
| Wiki manifest, sidebar, footer, publication | `AGENTS.md`, `docs/PROCEDURES.md` | [docs/WIKI.md](docs/WIKI.md) |
| Module list, exit codes, test doctrine | `AGENTS.md` | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Import into AutoClaw2, HARNESS, SagaAI | `docs/IMPORT.md` | `docs/IMPORT.md` (unchanged) |
| Recurring jobs with success criteria | `docs/PROCEDURES.md` | `docs/PROCEDURES.md` (unchanged) |
| Packaging, release, pre-commit, Action | not documented | [docs/PACKAGING.md](docs/PACKAGING.md) |

### 4. Expect one new warning

`ghagent doc --root .` now runs `agents.md-length`: an `AGENTS.md` longer than 120 lines is
reported as a **warning**, not an error, and the exit code stays `0`. The limit applies to the
root `AGENTS.md` of the examined tree only — `AGENTS.ru.md` and nested copies are not counted.
The fix is not to delete content: keep the map (purpose, install, one command per job, the
non-negotiable rules, the verification block, links) and move the detail into `docs/`, as this
repository now does. A silent `--ignore agents.md-length` is allowed, but then the file is not a
map and the person paying for it is the agent that reads it on every request.

### 5. Re-read the README contract before copying the new README

The README is now installation-first: package managers, optional PNG support, clone, Docker,
pre-commit and CI come before the internals, and the link bar points at `MIGRATION.md` and
`docs/PACKAGING.md`. The badge block changed with it: CI, the supported Python range, the licence,
the runtime dependency count and the self-test count are named there. The audit contract did not
move: 3–8 badges, one `H1`, a summary paragraph directly after it, installation, usage and licence
sections, a language tag on every fence. Copying the sections is fine; copying the numbers is
not, unless you measured them in your own repository.

### 6. Verify

```bash
ghagent selftest            # clone only
ghagent doc --root .
ghagent audit .
ghagent changelog check
ghagent assets check
ghagent privacy --root .
```

All six must exit `0`. `1` means error-level findings printed with `file:line`; `2` means a wrong
path or a command that needs the source tree.

## Nothing you must change

If you only run github-agent against your own repository and did not install the pack:

- **No file in your repository becomes required.** No new mandatory document, no new
  `.ghagent.json` field. The configuration file is still optional and its keys are unchanged.
- **No command is renamed or removed.** `audit`, `doc`, `privacy`, `assets`, `wiki`, `changelog`,
  `meta`, `install`, `verify-install`, `uninstall`, `snippet`, `report` and `selftest` keep their
  flags and exit codes `0`/`1`/`2`.
- **No new dependency appears.** Python 3.11+ and the standard library are still enough; Pillow
  remains an optional extra for PNG output.
- **The wiki, changelog and README contracts are unchanged.** The rules moved in this repository's
  documentation, not in the checker.
- **`agents.md-length` is a warning.** A long `AGENTS.md` in your repository lowers nothing except
  the quality of your own map; it does not fail the build.

The two changes that do ask for an action are choices, not requirements: reinstall the pack if
you want the new manifest version, and shorten `AGENTS.md` if you want to pay less context per
agent request.

## Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| `selftest` exits `2` right after `pip install github-agent` | the wheel ships the CLI only | clone the repository and run `python tools/ghagent.py selftest` from the clone |
| `install` exits `2` with "needs the source tree" | same | run `install` from a clone, not from the wheel |
| `agents.md-length` warns after upgrading | the file is over 120 lines | move detail into `docs/` and link it from the map |
| `ghagent --version` prints 1.1.0 after an upgrade | an older copy is first in `PATH`, or a virtual environment is active | reinstall in the environment that provides `ghagent`; check `pip list` |
| a pre-commit hook cannot find `ghagent` | the hook builds its own environment | pin the hook repository to `rev: v1.2.0`; no global install is needed |

Related: the rule catalogue is in [docs/RULES.md](docs/RULES.md), the packaging detail is in
[docs/PACKAGING.md](docs/PACKAGING.md), and the release history is in [CHANGELOG.md](CHANGELOG.md).
