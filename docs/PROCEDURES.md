# Procedures

Six jobs that repeat in every repository. For each: when it runs, which commands, what counts as
success, and what a failure means.

## 1. Auditing a repository

**When:** the project is published, the README was written long ago, metadata was filled in by
feel.

```bash
python tools/ghagent.py audit . --json > audit.json
python tools/ghagent.py audit --repo owner/name --http
python tools/ghagent.py report . --out AUDIT.md
```

**Success:** score at least 80%, no blocking findings, more than twenty items examined. A low
score is not a verdict but a work order: fix `error` first, `warn` second, leave `info`.

**Failure:** `remote.unavailable` means neither `gh` nor `GITHUB_TOKEN` is present. That is not
"all good": the metadata was not examined, and the report says so.

## 2. README, AGENTS.md and images

**When:** a new project, or the README stopped answering "how do I run this".

1. Start from `reference/readme-template.md` and `reference/agents-template.md`.
2. Fill in facts: commands, paths, versions, numbers with a source.
3. Render the banner: `python tools/ghagent.py assets render --write`, then place the image
   above the first section and run `assets check`.
4. Verify: `python tools/ghagent.py doc --root .`.

**Success:** one `H1`, a summary paragraph, at least three badges, installation, usage and
license sections present, every link alive, the banner referenced and the social preview
1280×640.

**Failure:** `md.toc` means the table of contents drifted from the headings. Do not fix it by
hand — an anchor is the heading lowercased with punctuation dropped and spaces turned into
hyphens.

## 3. Releasing a version

**When:** `[Unreleased]` has accumulated changes.

```bash
python tools/ghagent.py changelog check
python tools/ghagent.py changelog suggest --since v1.1.0
python tools/ghagent.py changelog release 1.2.0 --write
python tools/ghagent.py changelog notes 1.2.0 > release-body.md
gh release create v1.2.0 --notes-file release-body.md --title v1.2.0
```

**Success:** the new version has an ISO date, `[Unreleased]` is empty again, comparison links are
updated, `changelog check` is clean, and a human has read the release body.

**Failure:** `changelog.duplicate` means the version exists; `changelog.empty-version` means
there is nothing to release. An empty release makes the changelog meaningless.

## 4. The wiki

**When:** documentation outgrew the README, or a wiki exists without navigation.

```bash
python tools/ghagent.py wiki init --repo owner/name --title "Project name"   # when there is none
python tools/ghagent.py wiki build
python tools/ghagent.py wiki verify
python tools/ghagent.py wiki publish --repo owner/name                      # dry run
python tools/ghagent.py wiki publish --repo owner/name --push               # publish
```

The very first publication needs one manual step: `<repo>.wiki.git` is created by GitHub only
when a first page is saved in the web interface. Until then the command answers
`wiki.remote-missing` with that instruction instead of failing on a push.

**Success:** `build` and `verify` clean, the dry run shows only expected files, the `kept` list
has been read, and after `--push` the page opens.

**Failure:** `wiki.page-unlisted` means a file exists that the manifest does not list; such a
page is invisible, which is why it is an error. `wiki.image-relative` means the image lives
inside the wiki sources: move it into the repository tree and reference it by absolute URL.

## 5. Images

**When:** the repository has no picture, the link card looks empty, or a chart is needed in the
README.

```bash
python tools/ghagent.py assets suggest
python tools/ghagent.py assets render --title "Project" --tagline "What it does." --command "project --help" --write
python tools/ghagent.py assets check
```

**Success:** `assets/social-preview.png` is 1280×640, under 1 MB, referenced from the README with
alt text, and `assets check` exits `0`. Then upload the same file in **Settings → Social
preview** — that step is manual and the check prints it.

**Failure:** `assets.social-dimensions` means the image is smaller than 640×320 or not 1280×640;
`assets.svg-social` means an SVG was offered as a social preview, which the platform rejects;
`assets.missing-file` means the README points at a file that is not committed.

## 6. Metadata and publication

**When:** the repository is published, or the description and topics no longer match the content.

```bash
python tools/ghagent.py meta suggest
python tools/ghagent.py meta apply --repo owner/name --description "…" --topics a,b
python tools/ghagent.py meta apply --repo owner/name --description "…" --topics a,b --write
python tools/ghagent.py audit --repo owner/name --http
```

**Success:** the description is under 200 characters and starts with the category noun, topics
number 8–20 and are lowercase-hyphenated, the homepage answers `200`, and reading back after the
write matches the request.

**Failure:** `meta.topics-overflow` means more than twenty topics were requested and only twenty
are stored. `meta.verify` means the write did not land — read the response instead of trusting
the call.

## When everything is broken

1. `python tests/run_tests.py` — does the pack itself work.
2. `python tools/ghagent.py verify-install --profile <profile>` — is it the right copy.
3. `python tools/ghagent.py doc --root . --json` — what exactly is wrong, with file and line.
4. Only then edit files. Editing by feel restores the same defects.
