# github-agent

The pack for an agent that runs a GitHub repository and its wiki: audits hygiene, renders the
repository's images, builds and publishes the wiki, releases versions, keeps metadata honest.
Python 3, standard library only, no external dependencies.

## Start here

| Step | Page | Why |
|---|---|---|
| 1 | [Why this exists](01-Why) | which defects are caught, and why eyes cannot see them |
| 2 | [Installation](02-Install) | install the pack and prove it with its own tests |
| 3 | [File contracts](03-Repository-Contract) | what is checked in README, AGENTS.md, CHANGELOG |
| 4 | [Wiki workflow](04-Wiki-Workflow) | build, verify and publish without losing foreign pages |
| 5 | [Release](05-Release) | promote Unreleased, comparison links, release body |
| 6 | [Platform traps](06-Traps) | fifteen places where GitHub behaves unexpectedly |
| 7 | [Import into another agent](07-Import) | AutoClaw2, HARNESS, SagaAI |

## What the pack does

| Job | Command |
|---|---|
| Audit a repository | `ghagent.py audit .` |
| Documents and links | `ghagent.py doc --root .` |
| Images: banner and social preview | `ghagent.py assets render`, `check` |
| Wiki: build, verify, publish | `ghagent.py wiki build`, `verify`, `publish --push` |
| Changelog | `ghagent.py changelog check`, `release`, `suggest` |
| Metadata | `ghagent.py meta suggest`, `apply` |
| Install the skill | `ghagent.py install`, `verify-install` |

Every command returns an exit code: `0` clean, `1` findings at error level, `2` a usage problem.

## Links

- [Repository](https://github.com/paulmann/github-agent)
- [Releases](https://github.com/paulmann/github-agent/releases)
- [Issues](https://github.com/paulmann/github-agent/issues)
- Русская версия: [Домой](Home.ru)

> [!TIP]
> This wiki is built and verified by the pack itself: `wiki build` and `wiki verify`. If a page
> opens and its links lead to neighbouring pages, the checks work.
