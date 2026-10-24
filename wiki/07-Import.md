# Import into another agent

The pack is imported with two actions: a copy in the agent's skill root, and a rules line that
says where that copy is and how to prove it is intact.

## Skill roots

| Agent | Skill root | Rules file |
|---|---|---|
| AutoClaw2 | `%USERPROFILE%\.pi\agent\skills` | `%USERPROFILE%\.pi\agent\AGENTS.md` |
| HARNESS | `%USERPROFILE%\.dsh\skills` | `%USERPROFILE%\.dsh\AGENTS.md` |
| SagaAI | supplied by hand | the project `AGENTS.md` |

## Install

```bash
python tools/ghagent.py install --profile autoclaw --write
python tools/ghagent.py install --profile harness  --write
python tools/ghagent.py install --target <dir>     --write
```

The command copies the pack (tests included, so `selftest` works in place), writes
`.install.json` with a sha256 per file, and prints the rules block.

## The rules block

```bash
python tools/ghagent.py snippet --profile harness
```

The block names the pack path, requires reading the pack's own rules file, gives the verification
command and states one rule: one job, one command. The agent's rules files are not edited by the
command — that decision belongs to the owner.

## Verify

```bash
python tools/ghagent.py verify-install --profile harness
python tools/ghagent.py selftest
```

| Outcome | Exit | Meaning |
|---|---|---|
| `verify.ok` | 0 | the copy matches the installation |
| `verify.changed` | 1 | a file changed after installation |
| `verify.missing` | 1 | a file was deleted |
| `verify.manifest` | 1 | the directory was not installed by this pack |

## Update and remove

```bash
git -C <pack dir> pull
python tools/ghagent.py install --profile <profile> --write
python tools/ghagent.py verify-install --profile <profile>

python tools/ghagent.py uninstall --profile <profile> --write
```

`uninstall` refuses a directory without a manifest: it must not delete what another tool created.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| The agent does not see the skill | the directory exists, the agent ignores it | the skill list is read at session start — restart the session |
| The copy was edited by hand | `verify.changed` | reinstall |
| Installing into a foreign directory | `uninstall` refuses | pass `--target` explicitly |
| No tests in the distribution | `selftest` cannot find the runner | copy `tests/` with `tools/` |

## Next

- [Installation](02-Install).
- [Wiki workflow](04-Wiki-Workflow).
