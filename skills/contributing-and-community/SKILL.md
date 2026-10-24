---
name: contributing-and-community
description: GitHub community files — CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, issue and pull request templates, CITATION, GOVERNANCE, dependabot, release.yml and the community health score. Load when a repository opens to outside contributors, when GitHub shows an incomplete community profile, when issues arrive without the needed details, or when a security policy must be written.
---

# Community: the files GitHub reads

## What GitHub checks

`GET /repos/{owner}/{repo}/community/profile` returns `health_percentage` and the files it found.
A file is looked up in several places: the root, `.github/`, `docs/`.

| File | Purpose | Looked up in |
|---|---|---|
| `README.md` | the entrance | root, `.github/`, `docs/` |
| `LICENSE` | the legal permission to use the code | root |
| `CONTRIBUTING.md` | how to send changes | root, `.github/`, `docs/` |
| `CODE_OF_CONDUCT.md` | behaviour rules | root, `.github/`, `docs/` |
| `SECURITY.md` | how to report a vulnerability privately | root, `.github/`, `docs/` |
| `SUPPORT.md` | where to ask a question | root, `.github/`, `docs/` |
| `ISSUE_TEMPLATE/*` | the shape of a report | `.github/ISSUE_TEMPLATE/` |
| `PULL_REQUEST_TEMPLATE.md` | the shape of a change | root, `.github/`, `docs/` |
| `CODEOWNERS` | who reviews | `.github/`, root, `docs/` |
| `CITATION.cff` | how to cite the project | root |
| `GOVERNANCE.md` | who decides | root, `.github/`, `docs/` |

The checklist tick for issue templates appears only when the templates sit **exactly** in
`.github/ISSUE_TEMPLATE/` and carry valid keys: `name` and `about` for markdown templates,
`name` and `description` for YAML forms.

## Writing CONTRIBUTING

1. Verification commands in the first code block. Not "run the tests" — the exact command.
2. Acceptance rules: one change, one reason; new behaviour with a test; a new check with a
   fixture that fails without it.
3. Prohibitions: dependencies, secrets, real domains and addresses in examples.
4. Commit message convention and where the changelog lives.
5. What to attach to a bug report: version, environment, command, exit code, output without
   secrets.

## Writing SECURITY

- A supported-versions table first: it is what a reader looks for.
- A private channel (Security → Report a vulnerability), never a public issue.
- What to include, and the answer time.
- A threat model: which places are dangerous and how each is protected. That turns the policy
  from a formality into a document the product can be checked against.
- What the product does not do (send data, store credentials).

## Issue forms

- A YAML form beats free text: required fields force the version and the command.
- Three or four forms are enough: bug, feature request, application question, audit request.
- `config.yml` disables blank issues (`blank_issues_enabled: false`) and points at the security
  policy and support page.

## Verification

```bash
python <pack>/tools/ghagent.py audit .
python <pack>/tools/ghagent.py audit --repo owner/name
```

`audit` names the missing files (`repo.code-of-conduct`, `repo.support`, `repo.issue-forms`,
`repo.pr-template`, `repo.codeowners`, `repo.dependabot`); `audit --repo` prints the community
health percentage from the API.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| A template in `docs/` | no tick in the profile | move it to `.github/ISSUE_TEMPLATE/` |
| A YAML form without `description` | the form never appears | add `name` and `description` |
| A code of conduct without a contact | rules exist, nowhere to report | name a private channel |
| SECURITY without a versions table | nobody knows what is supported | add the table |
| A policy promising what the code does not do | a statement that cannot be verified | write only what holds |

## Done means

- `community/profile` reports at least 80%.
- Issue forms appear in the interface and require a version and a command.
- `SECURITY.md` names the channel, the answer time and the threat model.
- `CONTRIBUTING.md` starts with verification commands, not with thanks.
