# Wiki workflow

A GitHub wiki is a separate git repository (`<repo>.wiki.git`) with a flat namespace, two
navigation files and no access to the main repository tree. The pack turns `wiki/` plus a
manifest into a built tree, checks that tree, and only then publishes it. The pipeline exists so
that broken links and unlisted pages are caught locally instead of on the published wiki.

## Source layout

```text
wiki/
├─ wiki.json          manifest: the only ordering authority
├─ Home.md            landing page, mandatory
├─ 01-Why.md
├─ 02-Install.md
└─ 01-Why.ru.md       translation; a wiki page like any other
```

`wiki build` reads every `*.md` in `wiki/` (files starting with `_` are generated, not sources)
and writes the built tree to `.ghagent/wiki/`; `--out <dir>` writes elsewhere. The build
directory is deleted and recreated on every run.

## Manifest

`wiki/wiki.json` decides which pages exist, in which order, and under which sidebar group. A page
on disk that is missing from the manifest is `wiki.page-unlisted` (error): it would be invisible
in navigation, which is the same as lost. A page in the manifest that is missing on disk is
`wiki.page-missing` (error).

```json
{
  "repo": "owner/name",
  "branch": "main",
  "title": "Project name",
  "footer": "MIT",
  "groups": [
    {"title": "Start", "pages": ["Home.md", "01-Install.md"]},
    {"title": "Reference", "pages": ["02-API.md"]}
  ]
}
```

| Field | Meaning |
|---|---|
| `repo` | `owner/name`; used for absolute repository links, the sidebar and the footer. `wiki publish` still needs `--repo` or `owner_repo` in `.ghagent.json` |
| `branch` | branch named in absolute repository links (default `main`) |
| `title` | sidebar heading |
| `footer` | extra footer text, joined with repository and release links |
| `groups` | ordered groups; a group may carry a `labels` map to override a page label |

`reference/wiki-manifest-template.json` is the copyable starting point; `wiki init` scaffolds a
manifest plus `Home.md`, and with `--no-docs` it scaffolds no pages from `docs/`.

## Sidebar and footer

`_Sidebar.md` and `_Footer.md` are generated, never hand-edited. The sidebar carries the title,
a Home link, one block per manifest group, and — when `repo` is set — repository, releases and
issues links. The footer is a separator plus one line with repository and release links and the
`footer` text. `wiki verify` fails the built tree when either file is absent (`wiki.required`),
when the sidebar points at a page that does not exist (`wiki.sidebar-target`) and warns when a
page is reachable from nowhere (`wiki.page-orphan`).

## Build, verify, publish

```bash
ghagent wiki build                                  # wiki/ + wiki.json → .ghagent/wiki/
ghagent wiki verify                                 # check the built tree
ghagent wiki publish --repo owner/name              # dry run: shows added, modified, kept
ghagent wiki publish --repo owner/name --push       # actually push
```

Revision loop: edit `wiki/*.md` → `build` → `verify` → `publish` (dry run) → read the list →
`--push`. `verify` runs again inside `publish`; a non-zero verify refuses to publish unless
`--force` is passed, which is reserved for a human who accepts broken links.

What `build` rewrites, outside code fences only:

| Source link | Built link |
|---|---|
| `[x](02-Install.md)` where the page is in the manifest | `[x](02-Install)` |
| `[x](../README.md)` where the file exists in the repository | absolute `blob` URL on the manifest branch |
| `[x](../docs/RULES.md#traps)` | absolute `blob` URL plus the anchor |
| `[x](02-Install.md#usage)` | `[x](02-Install#usage)` |
| `[x](https://…)` | unchanged |

An image with a relative target is `wiki.image-relative` (error), not a warning: the wiki
repository cannot see the project tree, so the image would render as a broken box.

## Flat namespace

The wiki repository has no directories: `docs/page` cannot exist, a page is a filename in the
root. Internal links therefore carry no `.md` suffix and no path — `[Install](02-Install)`.
`wiki verify` reports `wiki.md-suffix` for a link that keeps the extension and `wiki.link-target`
for a link to a page that is not in the built tree. Cyrillic anchors work the same way as on
GitHub: lowercased, punctuation dropped, spaces to hyphens.

## Relative image trap

A README can reference `assets/social-preview.png` and it renders. The same line in a wiki page
cannot: the wiki is a different repository, so the path resolves against the wiki root. The fix
is to commit the image to the main repository and reference it by absolute URL:

```markdown
![Architecture](https://github.com/owner/name/raw/main/assets/architecture.png)
```

`wiki build` raises the error even when the file happens to exist in `wiki/`, because the built
wiki does not contain it.

## Remote-missing on first publication

GitHub creates `<repo>.wiki.git` only when the first page is saved in the web interface
(**Wiki → New page**); a push cannot create it. Until then `wiki publish --push` answers
`wiki.remote-missing` with that instruction instead of surfacing a raw git error. One page saved
by hand, then the normal publish cycle works. An initialized-but-empty wiki remote is reported as
`wiki.remote-empty`, not as a failure to clone.

## Prune policy

Publication keeps every page that exists on the remote and is not part of the build, and lists it
as `kept`. Deletion happens only with `--prune`, which is a human decision, not housekeeping:
remote wiki pages may be linked from issues, release notes and external sites. The dry run prints
the same list, so the decision is made before the push.
