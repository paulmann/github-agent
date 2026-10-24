# Checklists

Short lists for the moments when checking must be fast and thoughtless. The pack covers them with
commands; the lists remain for the decisions a human makes.

## Before publishing a repository

- [ ] Description: category first, under 200 characters, no emoji, no superlatives.
- [ ] Topics: 8–20, lowercase and hyphenated, the primary term first.
- [ ] Homepage: answers `200`, or is empty. A dead link is worse than none.
- [ ] README: title, summary paragraph, 3–8 badges, installation, usage, license.
- [ ] Every number in the README has a measurement source.
- [ ] `LICENSE` is detected by GitHub (`license.spdx_id` is not `NOASSERTION`).
- [ ] `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md` are present.
- [ ] Issue forms live in `.github/ISSUE_TEMPLATE/` and carry `name` and `description`.
- [ ] Banner rendered and referenced with alt text; `assets check` is clean.
- [ ] Social preview 1280×640, under 1 MB, uploaded in Settings.
- [ ] A release exists: tag `vX.Y.Z`, notes from the changelog, a checksummed asset.
- [ ] Wiki: `Home`, `_Sidebar`, `_Footer`, internal links verified.
- [ ] Pages: build `built`, URL answers `200`, canonical present.
- [ ] An inbound link from the owner's profile exists.

## Before publishing the wiki

- [ ] `ghagent wiki build` — no errors.
- [ ] `ghagent wiki verify` — no errors.
- [ ] Every page is in `wiki/wiki.json`, and every manifest entry exists.
- [ ] Internal links carry no `.md`.
- [ ] No relative images.
- [ ] `_Footer` contains absolute links only.
- [ ] The dry run was read: the `kept` list is understood.
- [ ] Publish with `--push`, then open the page in a browser.

## Before a release

- [ ] `CHANGELOG.md`: `[Unreleased]` holds entries, each about a visible change.
- [ ] `ghagent changelog release <version> --write`.
- [ ] `ghagent changelog check` — clean.
- [ ] One version everywhere: package manifest, `CITATION.cff`, the tag.
- [ ] `ghagent changelog notes <version>` — a human read the release body.
- [ ] Annotated tag, owner's signature.

## Before a pull request

- [ ] `python tools/ghagent.py selftest` — green.
- [ ] `python tools/ghagent.py doc --root .` — exit `0`.
- [ ] `python tools/ghagent.py audit .` — exit `0`.
- [ ] `python tools/ghagent.py assets check` — exit `0`.
- [ ] One logical reason for the change.
- [ ] A new check came with a fixture and a decoy.
- [ ] Documentation updated where behaviour changed, both language versions in one commit.

## What "green" means

A green run means the rules examined objects and found no violations. It does **not** mean the
project is in order: it means the agent starts from exact facts. If a rule examined zero objects,
the report says so in a separate `coverage.skipped` line.
