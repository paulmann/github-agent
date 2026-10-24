---
name: import-to-agents
description: Moving the repository-and-wiki skill into another agent — AutoClaw2, HARNESS, SagaAI: installing the pack into a skill root, the sha256 manifest, integrity verification, the rules line for AGENTS.md, updating and removal. Load when a skill must be connected to another agent, when the installed copy drifted from the tested one, or when an agent does not see the skill.
---

# Importing the skill into another agent

## What "import" means

Two things, both verifiable:

1. A copy of the pack sits in the agent's skill root, with `.install.json` next to it holding a
   sha256 per file.
2. The agent's rules (`AGENTS.md` or its equivalent) contain a line naming the copy, the
   verification command, and the rule "one job, one command".

The pack is self-contained: Python 3.11+ and the standard library. No `pip install`, no build, no
network during installation.

## Skill roots (measured, not guessed)

| Agent | Skill root | Rules |
|---|---|---|
| AutoClaw2 | `%USERPROFILE%\.pi\agent\skills` | `%USERPROFILE%\.pi\agent\AGENTS.md` |
| HARNESS | `%USERPROFILE%\.dsh\skills` | `%USERPROFILE%\.dsh\AGENTS.md` |
| SagaAI | supplied by hand | the project `AGENTS.md` or the agent's rules file |

## Install

```bash
python <pack>/tools/ghagent.py install --profile autoclaw --write
python <pack>/tools/ghagent.py install --profile harness  --write
python <pack>/tools/ghagent.py install --target <dir>     --write     # SagaAI
```

The command prints a ready rules block. Paste it into the agent's rules file — the command does
not edit foreign files.

## Verify

```bash
python <pack>/tools/ghagent.py verify-install --profile autoclaw
python <pack>/tools/ghagent.py selftest     # works inside the installed copy too
```

| Outcome | Exit | Meaning |
|---|---|---|
| `verify.ok` | 0 | the copy matches the installation |
| `verify.changed` | 1 | a file changed after installation |
| `verify.missing` | 1 | a file was deleted |
| `verify.manifest` | 1 | the directory was not installed by this pack — do not trust it |
| `verify.extra` | 0 | a file outside the manifest (information) |

## Update and remove

```bash
git -C <pack dir> pull
python <pack>/tools/ghagent.py install --profile <profile> --write
python <pack>/tools/ghagent.py verify-install --profile <profile>

python <pack>/tools/ghagent.py uninstall --profile <profile> --write
```

`uninstall` refuses a directory without a manifest: it has no right to delete what another tool
created. The rules block is removed from `AGENTS.md` by a human.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| The agent does not see the skill | the directory exists, the agent ignores it | the skill list is read at session start — restart the session |
| `%APPDATA%` is empty in a non-interactive session | a path is built as `\...` | take the home directory from `USERPROFILE`/`HOME` or the platform API |
| The copy was edited by hand | `verify.changed` | reinstall instead of patching in place |
| Installing into a foreign directory | `uninstall` refuses | pass `--target` explicitly |
| The pack ships without tests | `selftest` reports a missing runner | copy `tests/` together with `tools/` |

## Done means

- `verify-install` exits `0`.
- `selftest` inside the installed copy prints `PASS`.
- The rules block is in place and names the pack path and the verification command.
- A new agent session lists the skill.
