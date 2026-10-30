# Installation

Python 3.11 or newer is required (verified on 3.13; CI runs 3.11 and 3.13). There are no runtime
dependencies, and Pillow is optional: it only adds PNG output to `assets render`.

Three families of installation exist, and they are not equivalent. The package managers install
the CLI `ghagent` on its own. The git clone carries the whole pack — `tools/`, `tests/`,
`skills/`, `reference/`, `wiki/` and `docs/` — and is the only source of the `install`,
`verify-install`, `snippet` and `uninstall` commands. Docker and the GitHub Action need neither
Python nor a clone on the host.

## From PyPI: uv, pipx or pip

```bash
uv tool install github-agent-cli        # isolated tool environment
pipx install github-agent-cli           # isolated virtual environment
pip install github-agent-cli            # into the active environment
ghagent --version                   # github-agent 1.2.1
```

The console script is `ghagent`; the distribution is `github-agent`. The wheel ships the CLI
only, so in a wheel installation `selftest` and `install` exit `2` with a message that points at
the git clone. That is deliberate: the tests and the skill templates are not part of the wheel.

## Optional PNG support

`assets render` always writes the SVG. PNG output needs Pillow:

```bash
pip install "github-agent-cli[png]"
uv tool install --with pillow github-agent-cli
```

Without Pillow the command produces the SVG and says why no PNG exists.

## From the repository

The clone is the development install and the source of the pack operations:

```bash
git clone https://github.com/paulmann/github-agent.git
cd github-agent

python tools/ghagent.py --version
python tools/ghagent.py selftest
pip install -e .                    # optional: the `ghagent` command from this checkout
```

`selftest` runs the pack's own tests and prints `PASS` with exit `0`. If the tests fail, do not
work with this copy: take a clean one.

## Docker

The image is built from the checkout, so it does not need a PyPI release:

```bash
docker build -t ghagent .
cd /path/to/your/repository
docker run --rm -v "$PWD:/repo" ghagent audit .
```

The working directory is `/repo` and the entry point is `ghagent`. No registry image is
published as part of 1.2.1; the tag is a local convention. The image contains the CLI only, so
`selftest` and `install` exit `2` there as well. Details: [Docker example](https://github.com/paulmann/github-agent/blob/main/examples/docker.md).

## GitHub Action

The composite action installs the pack from its own checkout, so it works as soon as the tag
exists:

```yaml
- uses: actions/checkout@v7
- uses: paulmann/github-agent@v1.2.1
  with:
    command: audit .
    min-score: "80"
```

Inputs: `command` (default `audit . --min-score 80`), `min-score`, `working-directory`,
`python-version`, `github-token`. A complete workflow: [CI usage](https://github.com/paulmann/github-agent/blob/main/examples/ci-usage.md).

## First audit

```bash
cd <your repository>
ghagent audit .
```

Inside a clone the same command is `python tools/ghagent.py audit .`. The command prints the
hygiene score, items with their status, and findings as `file:line` with a rule id.

| Exit code | Meaning |
|---|---|
| `0` | no blocking findings |
| `1` | findings at error level |
| `2` | usage or environment error: wrong path, missing file, missing token |

## Install the skill into an agent

This step needs the clone, because it copies the pack, not the CLI:

```bash
python tools/ghagent.py install --profile autoclaw --write   # AutoClaw2
python tools/ghagent.py install --profile harness  --write   # HARNESS
python tools/ghagent.py install --target <dir>     --write   # SagaAI
```

The command copies the pack into the skill root, writes `.install.json` with a sha256 per file,
and prints the rules block for `AGENTS.md`. Details: [Import into another agent](07-Import).

## Verify the installation

```bash
ghagent --version                            # wheel or editable install
python tools/ghagent.py selftest             # clone only
python tools/ghagent.py verify-install --profile autoclaw
```

`verify-install` answers one question: is the installed copy still the one that passed the tests.
`verify.ok` with exit `0` means yes; any drift is printed with the file name. A version mismatch
between `ghagent --version` and the release you meant to install means the wrong environment on
`PATH`, not a broken pack.

## Environment

| What | Requirement |
|---|---|
| Python | 3.11+ |
| `git` | needed by `changelog suggest` and `wiki publish` |
| `gh` CLI or `GITHUB_TOKEN` | needed only by `audit --repo`, `meta`, `wiki publish` |
| Network | only for the commands that talk to GitHub |
| Pillow | optional, enables PNG rendering in `assets render` |
| pre-commit | optional, runs the hooks from a released tag |

The rest works offline: `doc`, `audit .`, `changelog check`, `changelog release`, `wiki build`,
`wiki verify`, `assets check`.

## Next

- [File contracts](03-Repository-Contract) — what is checked.
- [Wiki workflow](04-Wiki-Workflow) — build and publish.
- [Packaging and release](https://github.com/paulmann/github-agent/blob/main/docs/PACKAGING.md) —
  wheel, sdist, Action, Docker and the publish procedure.
