# Governance

## Roles

| Role | Who | Rights |
|---|---|---|
| Maintainer | the repository owner | merge, releases, wiki publication, metadata |
| Contributor | anyone opening a pull request | code and documentation through pull requests |
| User | any reader | issues, discussions |

## How a change is accepted

1. An issue describes the problem: what is wrong, what proves it, what should change.
2. A pull request carries the change, a fixture (if a rule changes), and an entry under
   `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
3. `python tests/run_tests.py`, `ghagent doc --root .` and `ghagent audit .` are green.
4. The maintainer merges; a disagreement is settled by a measurement, not an opinion.

## How a version is released

Semantic versioning: `fix` is a patch, `feat` is a minor, a breaking change is a major.

```bash
python tools/ghagent.py changelog release <version> --write
python tools/ghagent.py changelog check
git tag -a v<version> -m "v<version>"
python tools/ghagent.py changelog notes <version> > release-body.md
```

## What this project does not have

- Hidden decision channels: every change is visible in the repository history.
- Dependencies to install: the pack runs on the standard library.
- A committee: the project is maintained by one person, and that is written down so no one
  mistakes it for collective governance.
