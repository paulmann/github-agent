# Importing the pack into another agent

The pack needs no system installation: it is a directory you call by path. "Importing" means
two things — a copy of the pack inside the agent's skill root, and a rules line that tells the
agent where that copy is and how to prove it is intact.

## What is copied

`install` copies `AGENTS.md`, the root documents, `CITATION.cff`, and the `skills/`, `tools/`,
`tests/`, `reference/`, `docs/`, `wiki/`, `.github/` directories, then writes `.install.json`
with a sha256 per file. The tests come along on purpose: without them neither `selftest` nor any
proof that the installed copy behaves as tested is possible.

## AutoClaw2

Skill root: `%USERPROFILE%\.pi\agent\skills`; rules: `%USERPROFILE%\.pi\agent\AGENTS.md`.

```powershell
git clone https://github.com/paulmann/github-agent.git "$env:USERPROFILE\src\github-agent"
Set-Location "$env:USERPROFILE\src\github-agent"

python tools\ghagent.py install --profile autoclaw --write
python tools\ghagent.py verify-install --profile autoclaw
python tools\ghagent.py snippet --profile autoclaw
```

Paste the printed block into `%USERPROFILE%\.pi\agent\AGENTS.md`. The skill list is read at
session start, so a new skill appears in the next session, not in the current one.

## HARNESS

Skill root: `%USERPROFILE%\.dsh\skills`; rules: `%USERPROFILE%\.dsh\AGENTS.md`.

```powershell
python tools\ghagent.py install --profile harness --write
python tools\ghagent.py verify-install --profile harness
python tools\ghagent.py snippet --profile harness
```

## SagaAI

There is no measured skill root for SagaAI, so the path is supplied explicitly. If the agent
reads rules from the project's `AGENTS.md`, naming the pack path and the verification command
there is enough — the pack is self-contained.

```bash
git clone https://github.com/paulmann/github-agent.git <dir>
python tools/ghagent.py install --target <saga-skill-root> --write
python tools/ghagent.py snippet --target <saga-skill-root>
```

`snippet` prints text, it does not write a file: where that block belongs is the owner's
decision.

## Verifying an import

```bash
python tools/ghagent.py verify-install --profile <autoclaw|harness>   # 0 means the copy is intact
python tools/ghagent.py --version
```

| Outcome | Meaning | Action |
|---|---|---|
| `verify.ok`, exit `0` | the copy matches the installation manifest | work |
| `verify.changed`, exit `1` | a file changed after installation | reinstall |
| `verify.missing`, exit `1` | a file was deleted | reinstall |
| `verify.manifest`, exit `1` | the directory was not installed by this pack | do not trust it, install again |
| `verify.extra`, `info` | a file outside the manifest | check whether it is debris |

## Updating

```bash
git -C <pack dir> pull
python tools/ghagent.py install --profile <profile> --write
python tools/ghagent.py verify-install --profile <profile>
```

`install` overwrites files and rewrites the manifest, so `verify` is green again afterwards. The
previous copy is not archived: git restores it in one step.

## Removing

```bash
python tools/ghagent.py uninstall --profile <profile> --write
```

Removal without `.install.json` is refused: the command has no right to delete a directory
another tool created. The rules block in the agent's `AGENTS.md` is removed by hand — the pack
does not edit foreign rule files.
