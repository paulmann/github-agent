---
name: github-wiki
description: Running a GitHub wiki as project documentation — pages in the repository, an order manifest, _Sidebar and _Footer, link rewriting for the flat namespace, build, verify and publish. Load when documentation outgrew the README, when a wiki exists without navigation, when links lead nowhere or images do not render.
---

# A wiki that works

## What must be known before the first page

| Platform property | Consequence |
|---|---|
| A wiki is a separate git repository, `<repo>.wiki.git` | it cannot see the project tree |
| The namespace is flat | no subdirectories; a page is a file in the wiki root |
| A page link carries no `.md` | `[Installation](01-Install)` |
| `_Sidebar.md` and `_Footer.md` are the only navigation | without them pages are not found |
| A relative image does not work | commit it to the repository, reference an absolute URL |
| The page title is the filename | renaming a file changes the URL |
| Only wikis with 500+ stars and public editing disabled are indexed | use GitHub Pages for discovery |
| A private wiki needs a paid plan | do not promise it |
| The wiki repository is not created by a push | save the first page in the web interface first |

## Structure in the repository

```text
wiki/
  wiki.json      manifest: order, groups, title, repository link
  Home.md        first page (canonical, English)
  Home.ru.md     translation, published as Home.ru
  01-Install.md
```

Every file must be in the manifest, and every manifest entry must exist. Otherwise `wiki build`
fails: an invisible page is treated as lost, and an empty link as a defect.

## Build and verify

```bash
python <pack>/tools/ghagent.py wiki build
python <pack>/tools/ghagent.py wiki verify
```

`build` rewrites pages into `.ghagent/wiki/`: internal links lose `.md`, links into the
repository tree become `https://github.com/<owner>/<repo>/blob/<branch>/…`, and a relative image
becomes an error. `verify` checks the built tree: `Home`/`_Sidebar`/`_Footer` exist, links point
at existing pages, no page is missing from navigation, every page has an `H1`.

## Publishing

```bash
python <pack>/tools/ghagent.py wiki publish --repo owner/name            # dry run
python <pack>/tools/ghagent.py wiki publish --repo owner/name --push     # publish
```

1. **The dry run is mandatory.** It prints what will be added, what changed and what is **kept**.
2. **Nothing foreign is deleted.** Remote pages absent from the build are kept; deletion requires
   `--prune` and a look at the list.
3. **Verification gates publication.** `publish` refuses a tree with errors; `--force` is a
   deliberate decision, not a workaround.
4. **`Home.md` is mandatory.** Publication does not start without it.

## Anchors and cross-links

- An anchor is the heading lowercased, punctuation dropped, spaces turned into hyphens.
- An em dash in a heading produces a **double** hyphen: `## Ship — fast` → `#ship--fast`.
- A repeated heading gets `-1`, `-2`.
- Compare anchors case-insensitively: the platform's own documentation contradicts itself on a
  capital Greek letter.

## Traps

| Trap | Symptom | Action |
|---|---|---|
| The wiki repository does not exist yet | `Repository not found` on publish | save the first page in the web interface (Wiki → New page) |
| A page missing from the manifest | not reachable from navigation | add it to `wiki.json` |
| A link with `.md` | raw file or 404 | drop the extension |
| An image inside `wiki/` | does not render | move it into the repository tree, reference absolutely |
| `--prune` without reading the list | a foreign page is gone | restore it from the wiki repository history |

## Done means

- `wiki build` and `wiki verify` exit `0`.
- The dry run shows only expected files and the `kept` list has been read.
- After `--push` the page opens, navigation works, links do not 404.
