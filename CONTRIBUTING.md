# Contributing

Thanks for the interest. The project is small, and every rule here is verifiable: if a change
cannot be proven by a command that exits `0`, it is not ready. Start with [AGENTS.md](AGENTS.md)
for the map, [docs/RULES.md](docs/RULES.md) for the rule catalogue and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the modules fit together.

## Repository layout

| Path | What is there |
|---|---|
| `AGENTS.md` | the map an agent reads first; `AGENTS.ru.md` mirrors it |
| `docs/RULES.md` | full rule catalogue, file contracts, traps, enforcement map |
| `docs/WIKI.md` | wiki manifest, build, verify, publish |
| `docs/ARCHITECTURE.md` | modules, exit codes, report model, test doctrine |
| `docs/PACKAGING.md` | PyPI, wheel and sdist, Action, Docker, pre-commit |
| `tools/ghagent.py` | the CLI entry point |
| `tools/ghalib/` | the library: one module per area |
| `tests/run_tests.py` | the whole test suite, run by `ghagent selftest` |
| `reference/` | README, AGENTS, CHANGELOG, CONTRIBUTING and wiki templates |
| `wiki/` | wiki sources plus `wiki.json` |
| `scripts/` | `build_and_check.sh` and `build_and_check.ps1` |

## Development setup

```bash
git clone https://github.com/paulmann/github-agent.git
cd github-agent
pip install -e .
ghagent --version           # github-agent 1.2.1
ghagent selftest            # must print PASS
python tests/run_tests.py   # the same suite, full output
```

Python 3.11 or newer; no runtime dependencies. Pillow is optional (`pip install -e ".[png]"`) and
only adds PNG output to `ghagent assets render`.

## Adding a rule

A rule is not a line of code; it is a proof that the code can fail. Every pull request that adds
or changes a check carries all five parts:

1. **Implementation** in the owning module under `tools/ghalib/`, with a rule id that follows the
   existing prefixes (`doc.`, `md.`, `privacy.`, `repo.`, `readme.`, `changelog.`, `assets.`,
   `wiki.`, `meta.`, `install.`, `verify.`, `agents.`). The id is what a reader greps in CI.
2. **A failing fixture** in `tests/run_tests.py` — the smallest tree on which the rule must report
   the expected id at the expected level. A rule without a failing fixture is rejected: it cannot
   be shown to exist.
3. **A decoy** — a neighbouring tree on which the same rule must stay quiet. A rule that cannot
   distinguish a defect from a legitimate case produces false `FAIL`s, which are worse than no
   check.
4. **Documentation** in [docs/RULES.md](docs/RULES.md): the id, the level, what it examines and
   which command produces it. If the rule changes a file contract, update the contract section in
   the same file.
5. **The map** in [AGENTS.md](AGENTS.md) only when the rule changes what an agent must do. The map
   is under 120 lines on purpose (`agents.md-length` warns above that) — detail belongs in `docs/`.

A false `PASS` is worse than a false `FAIL`: a rule that examined zero objects must report
`coverage.skipped` instead of returning a green verdict. Two tests are worth adding with any new
rule: one that proves the finding fires, one that proves the count of examined objects is what the
message claims.

## Before a pull request

Run all six from the repository root and keep the output; every one must exit `0`:

```bash
ghagent selftest
ghagent doc --root .
ghagent audit .
ghagent changelog check
ghagent assets check
ghagent privacy --root .
```

`selftest` needs the clone (`tests/` is not in the wheel); in a wheel installation it exits `2` by
design. `audit` scores the tree — a score below 80 is a warning, below 60 an error. `doc` is the
documentation and link check; do not silence with `--ignore` what can be fixed, and when
`--ignore` is right the skipped ids are listed in the JSON field `rules_ignored`.

## Packaging check

Changes that touch packaging, the entry point, `pyproject.toml` or the release workflow add one
more command. It builds the source distribution and the wheel, runs `twine check`, compares the
artefact version with `PACK_VERSION` in `tools/ghalib/util.py`, proves the wheel layout (flat
`ghagent.py` plus `ghalib/`, no `tools` package), proves there is no third-party runtime
dependency, installs the wheel into a clean virtual environment and runs the installed CLI:

```powershell
pwsh -NoProfile -File scripts/build_and_check.ps1
```

```bash
bash scripts/build_and_check.sh
```

It prints `PASS` on success and writes nothing into the repository (everything happens in a
temporary directory). The packaging model is described in [docs/PACKAGING.md](docs/PACKAGING.md).

## Documentation language

English is canonical. A translation carries the `.ru.md` suffix (`README.ru.md`, `AGENTS.ru.md`,
`docs/IMPORT.ru.md`) and is updated in the same commit as the original — a translation that
silently lags is a defect, not a backlog item. New pages follow the same pattern: `NAME.md` plus
`NAME.ru.md`. The wiki pages follow it too, and the new page is listed in `wiki/wiki.json` in the
same change.

## Text and encoding

Files are UTF-8 without BOM and use LF line endings; prose is wrapped near 100 characters, code
fences carry a language tag, tables are aligned to their header count. `ghagent doc --root .`
checks all of it, including anchors: a heading anchor is the heading lowercased, punctuation
dropped and spaces turned into hyphens.

## Commits and changelog

Conventional Commits, one logical change per commit: `feat:`, `fix:`, `docs:`, `perf:`,
`refactor:`, `test:`, `chore:`, `security:`. A breaking change carries `!` in the header or
`BREAKING CHANGE:` in the body, and its size — relative to the module boundary — is argued in the
body rather than implied. The subject is imperative and lower-case after the colon.

The changelog entry is written by a human: `ghagent changelog suggest --since v1.1.0` drafts from
commit subjects into the Keep a Changelog sections, and a reviewer decides what a user can see.
`ghagent changelog check` must pass before tagging.

## Dependencies

No runtime dependencies. The pack is installed by copying a directory and must keep working on a
bare Python 3.11 with no network access; that constraint is the reason it is adopted. Pillow stays
an optional extra and only affects PNG rendering. `scripts/build_and_check.ps1` fails the build if
the wheel declares a non-extra `Requires-Dist`.

## Security

Never commit tokens, passwords, private keys, personal e-mail addresses or absolute machine paths.
`ghagent privacy --root .` and the same scan inside `ghagent doc` block the build if one appears;
the accepted placeholders are `<token>`, `<path>`, `example.com` and
`user@users.noreply.github.com`. Report a vulnerability the way [SECURITY.md](SECURITY.md)
describes, privately, instead of opening a public issue. If a secret is committed anyway, rotate
it first and then clean the history — deleting the file in a new commit does not remove it.

## Reporting a bug

Include the version (`ghagent --version`), the Python version, the operating system, the exact
command, the exit code and the `--json` output. For a repository-specific problem, attach the
smallest tree fragment that reproduces it, with secrets removed.
