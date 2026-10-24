<!-- ghagent: template -->
# Contributing

## Before a pull request

```bash
<test command>
<lint command>
<secret scan>
```

Every command must exit `0`.

## Rules

- One pull request, one logical reason.
- New behaviour arrives with a test; a new check arrives with a fixture that fails without it.
- Do not add dependencies without a discussion: <the reason this project stays dependency-free>.
- Do not commit secrets, real domains, IP addresses or personal data. Use `example.com`,
  `203.0.113.0/24`, `user@users.noreply.github.com`.
- Style: <link to the style guide>.

## Language of documentation

English files are canonical; translations carry a language suffix (`README.ru.md`) and are
updated in the same commit.

## Commit messages

Conventional Commits: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, `test:`, `chore:`. A
breaking change is marked with `!` in the header or `BREAKING CHANGE:` in the body.

## Reporting a bug

Include the version, the environment, the exact command, the exit code, and the output without
secrets.
