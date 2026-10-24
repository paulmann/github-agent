# Support

## Where to ask

| Question | Where |
|---|---|
| A command misbehaves | issue via the "Bug report" form |
| A check should exist | issue via the "Feature request" form |
| A vulnerability | privately, per [SECURITY.md](SECURITY.md) |
| How to apply the pack to your repository | issue via the "Repository audit request" form |

## What to include

- the pack version: `python tools/ghagent.py --version`;
- the Python version: `python -V`;
- the command in full, and its exit code;
- the output of `--json`: it contains paths and rule ids but not file contents;
- for wiki questions, `wiki/wiki.json` with personal data removed.

## What to expect

The project is maintained by one person, so answers are not instant. An accepted bug appears in
`[Unreleased]` of [CHANGELOG.md](CHANGELOG.md) immediately, not "at some point".

## Language

Issues and pull requests are welcome in English or Russian. The documentation follows the same
rule: English files are canonical, `*.ru.md` carries the translation.
