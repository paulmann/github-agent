# Contributing

Thanks for the interest. The project is small, so the rules are short and verifiable.

## Before a pull request

```bash
python tests/run_tests.py
python tools/ghagent.py doc --root .
python tools/ghagent.py audit .
python tools/ghagent.py assets check
```

All four commands must exit `0`. If the change touches a rule, the same pull request adds a
fixture that fails without it and a decoy on which the rule must stay quiet.

## Rules

- One pull request, one logical reason. Describe the motivation and the verification scenario.
- A check without a fixture is not accepted: a rule that cannot be proven is removed, not
  documented.
- A false `FAIL` is worse than no check; a false `PASS` is worse than a false `FAIL`. A rule that
  examined zero objects must say so.
- No external dependencies. The pack runs on the Python standard library, so another agent can
  install it with a single `git clone`. Pillow stays optional and only affects PNG rendering.
- Text files are UTF-8 without BOM, LF line endings, four-space indentation.
- Do not commit tokens, passwords, personal addresses or absolute machine paths. Use
  `<placeholder>`, `example.com`, `user@users.noreply.github.com`.
- Documentation changes with the code: if a command behaves differently, update
  [AGENTS.md](AGENTS.md) and [README.md](README.md).

## Language of documentation

English files are canonical. Russian translations carry the `.ru.md` suffix and are updated in
the same commit as the original — a translation that silently lags is a defect, not a backlog
item. New pages follow the same pattern: `NAME.md` plus `NAME.ru.md`.

## Commit messages

Conventional Commits: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, `test:`, `chore:`. A
breaking change is marked with `!` in the header or `BREAKING CHANGE:` in the body. The changelog
draft is produced by `ghagent changelog suggest`, but the entry itself is written by a human.

## Reporting a bug

Include the Python version, the operating system, the exact command, the exit code, and the
output of `--json`. For repository-specific problems, attach the relevant tree fragment without
secrets.
