# Installation

Python 3.11 or newer is required (verified on 3.13.15). No `pip install`, no build step, no
system packages. Pillow is optional and only adds PNG rendering.

## From the repository

```bash
git clone https://github.com/paulmann/github-agent.git
cd github-agent

python tools/ghagent.py --version
python tools/ghagent.py selftest
```

`selftest` runs the pack's own tests and prints `selftest: PASS` with exit `0`. If the tests fail,
do not work with this copy: take a clean one.

## First audit

```bash
cd <your repository>
python <path>/github-agent/tools/ghagent.py audit .
```

The command prints the hygiene score, items with their status, and findings as `file:line`.

| Exit code | Meaning |
|---|---|
| `0` | no blocking findings |
| `1` | findings at error level |
| `2` | usage error: wrong path, missing file |

## Install the skill into an agent

```bash
python tools/ghagent.py install --profile autoclaw --write   # AutoClaw2
python tools/ghagent.py install --profile harness  --write   # HARNESS
python tools/ghagent.py install --target <dir>     --write   # SagaAI
```

The command copies the pack into the skill root, writes `.install.json` with a sha256 per file,
and prints the rules block for `AGENTS.md`. Details: [Import into another agent](07-Import).

## Verify the installation

```bash
python tools/ghagent.py verify-install --profile autoclaw
```

`verify.ok` with exit `0` means the installed copy matches the tested one. Any drift is printed
with the file name.

## Environment

| What | Requirement |
|---|---|
| Python | 3.11+ |
| `git` | needed by `changelog suggest` and `wiki publish` |
| `gh` CLI or `GITHUB_TOKEN` | needed only by `audit --repo`, `meta`, `wiki publish` |
| Network | only for the commands that talk to GitHub |
| Pillow | optional, enables PNG rendering in `assets render` |

The rest works offline: `doc`, `audit .`, `changelog check`, `changelog release`, `wiki build`,
`wiki verify`, `assets check`.

## Next

- [File contracts](03-Repository-Contract) — what is checked.
- [Wiki workflow](04-Wiki-Workflow) — build and publish.
