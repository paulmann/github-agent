# Wiki workflow

The wiki is maintained from the repository: pages live in `wiki/`, order is set by
`wiki/wiki.json`. Publication is a separate step performed by the pack.

## Why not edit the wiki on GitHub

| Approach | Problem |
|---|---|
| Editing in the wiki web interface | drifts from the repository, no review |
| Pages copied in two places | a month later they differ |
| Publishing by hand with `git clone .wiki.git` | the verification step is forgotten and foreign pages are lost |

The pack keeps the source in the repository, where review and CI work, and the wiki receives a
built tree.

## Build

```bash
python tools/ghagent.py wiki build
python tools/ghagent.py wiki verify
```

What `build` does:

1. Reads `wiki/wiki.json`; every manifest entry must exist.
2. Every file in `wiki/` must be listed — otherwise "the page is invisible", which is an error.
3. Rewrites links: internal ones lose `.md`, links into the repository tree become absolute
   `https://github.com/<owner>/<repo>/blob/<branch>/…`.
4. A relative image is an error: the wiki repository cannot see the project tree.
5. Generates `_Sidebar.md` from the manifest groups and `_Footer.md` with repository links.

`verify` checks the built tree: required files, links to existing pages, no `.md` inside internal
links, no relative images, an `H1` per page, every page reachable from navigation.

## Publish

```bash
python tools/ghagent.py wiki publish --repo owner/name            # dry run
python tools/ghagent.py wiki publish --repo owner/name --push     # publish
```

| Flag | Effect | When |
|---|---|---|
| no flags | commits into the local clone, sends nothing | always first |
| `--push` | sends to `<repo>.wiki.git` | after reading the dry run |
| `--prune` | deletes remote pages absent from the build | deliberately, never by habit |
| `--force` | publishes even when verification failed | almost never |
| `--author-name`, `--author-email` | the commit signature | the owner's identity, not the agent's |

Output: added, modified, kept pages and the commit hash. Pages on the server that the build does
not contain are **kept** by default, so foreign work is never lost silently.

The first publication needs one manual step: `<repo>.wiki.git` is created by GitHub only when a
first page is saved in the web interface, and `git push` cannot create it. Until then the command
returns `wiki.remote-missing` with that instruction.

## What to write on a page

1. `H1` — the page name, matching the filename without `.md`.
2. A paragraph: why this page exists.
3. A table or a list: specifics, not reasoning.
4. A language-tagged code block for every command.
5. At the end, a link to the next page or the repository.

## Translations

English pages are canonical. A Russian translation is a separate page with the `.ru.md` suffix and
appears in navigation under its own group. Build and verify treat both exactly the same way: a
translation gets no exemption from link and image rules.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| The wiki repository does not exist | `remote: Repository not found` on publish | save the first page in the web interface, then publish |
| A link with `.md` | raw file or 404 | drop the extension |
| An image inside `wiki/` | does not render | move it into the repository tree, reference absolutely |
| A page missing from the manifest | absent from navigation | add it to `wiki.json` |
| A Cyrillic anchor | `#Установка` is not found | compare case-insensitively, write it as the heading reads |
| `--prune` without reading the list | a page is gone | restore it from the wiki repository history |

## Next

- [Release](05-Release).
- [Platform traps](06-Traps).
