# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.1.x | yes |
| 1.0.x | yes |
| < 1.0.0 | no |

## Reporting a vulnerability

Use the private channel: the **Security** tab → **Report a vulnerability**. Do not open a public
issue; a vulnerability report in a public tracker discloses it before a fix exists.

Include:

- the pack version (`python tools/ghagent.py --version`) and the Python version;
- the command that reproduces the problem and its output;
- what the risk actually is: which file is read, overwritten or published.

Expect an answer within seven days. An accepted vulnerability is fixed on a branch, then a patch
release carries a `Security` entry in [CHANGELOG.md](CHANGELOG.md).

## Threat model

The pack works on a local tree and with the GitHub API on behalf of the owner. The dangerous
places:

| Place | Risk | Protection |
|---|---|---|
| `wiki publish --push` | overwriting or deleting someone else's pages | without `--push` it is a dry run; pages the build does not contain are kept, deletion requires `--prune` |
| `wiki publish` with an empty manifest | publishing an empty wiki | an empty page set is an error before any write |
| `meta apply --write` | replacing the topic list | the list is merged with the existing one; `--replace-topics` is a separate flag |
| `install` / `uninstall` | deleting a foreign directory | `uninstall` requires the `.install.json` manifest and refuses otherwise |
| `doc` / `audit` / `privacy` | reading files that contain secrets | values are never printed: a finding names the rule, the path and the line |
| `changelog release --write` | corrupting the changelog | the file is validated again after writing, and errors are reported immediately |
| `assets render` | overwriting an existing image | files are written only with `--write`, and the target names are fixed |

## What the pack does not do

- It sends nothing anywhere except `api.github.com`, and only for `audit --repo`, `meta` and
  `wiki publish`.
- It stores no credentials and prints none: it uses the existing `gh` authorisation or the
  `GITHUB_TOKEN` variable.
- It never runs `git push --force` and never rewrites history.
