## What changed

<!-- One paragraph: what the pull request does and why. -->

## Why

<!-- The problem it solves. Link the issue if there is one. -->

## How it was verified

- [ ] `python tests/run_tests.py` — all checks pass
- [ ] `python tools/ghagent.py doc --root .` — exit code 0
- [ ] `python tools/ghagent.py audit .` — exit code 0

## Checklist

- [ ] One logical change; no unrelated edits
- [ ] A new rule brought a fixture that fails without the change and a decoy that must stay quiet
- [ ] Documentation updated (AGENTS.md / README.md) if behaviour changed
- [ ] `[Unreleased]` in CHANGELOG.md mentions the user-visible change
