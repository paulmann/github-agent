---
name: github-repo
description: Running a GitHub repository as a product — description, topics, homepage, README, hygiene files, releases. Load when a repository needs to be audited or rebuilt, when a README must be written, when metadata has to match the content, or before announcing a project.
---

# Repository as a product

## When to load

- The repository exists but is invisible: a three-word description, no topics, a README that
  opens with philosophy instead of installation.
- A README is needed that people finish.
- A pre-publication check is needed: community files, license, links, badges.

## First call

```bash
python <pack>/tools/ghagent.py audit . --json
python <pack>/tools/ghagent.py audit --repo owner/name
```

`audit` answers with one structure: the hygiene score, items with `pass|fail|warn|skipped`, and
findings with `file:line`. Items that could not be examined land in `skipped` and do **not**
raise the score.

## What decides discoverability

| Field | Rule | Why |
|---|---|---|
| `description` | category noun first, under 200 characters, no emoji, no superlatives | search shows the first ~120 characters |
| `topics` | 8–20, lowercase and hyphenated, primary term first | the only structured keyword field |
| `homepage` | answers `200`, or empty | a dead link is worse than none |
| `LICENSE` | detected by GitHub: `spdx_id` is not `NOASSERTION` | otherwise the project is legally unusable |
| README | title, banner, badges, installation, usage, license | the first thirty seconds decide |
| Images | a 1280×640 social preview and a README banner | link cards look empty without them |
| Wiki | `Home`, `_Sidebar`, `_Footer` | navigation turns pages into documentation |
| Release | tag `vX.Y.Z` with notes | the signal that the project is alive |

## Order of work

1. `audit .` — find the failures; fix `error` before `warn`.
2. README: start from `reference/readme-template.md`, fill in facts, check with
   `ghagent doc --root .`.
3. Images: `ghagent assets render --write`, then `assets check`.
4. Metadata: `ghagent meta suggest`, then `meta apply ... --write`.
5. Read back: `ghagent audit --repo owner/name --http`.
6. Report: `ghagent report . --out AUDIT.md`.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| `PUT /topics` replaces the list | topics you did not touch disappear | merge with the existing set, re-read |
| More than 20 topics | some are silently dropped | keep 20, primary term first |
| Pages in a private repository | `422 Your current plan does not support GitHub Pages for this repository` | the free plan does not allow it |
| Pages builds are asynchronous | 404 right after enabling | poll the build, then the URL |
| `gh api --jq .content` for a README | base64 with line breaks | `-H 'Accept: application/vnd.github.raw'` |
| A badge pointing at a missing workflow | the badge renders as "not found" | the badge path is the workflow path |

## Done means

- `ghagent audit .` exits `0` with a score of at least 80%.
- `ghagent audit --repo owner/name` exits `0`.
- Every number in the README names its source.
- The description contains nothing a reader cannot verify.
