# Platform traps

Fifteen places where GitHub behaves differently from what a person writing documentation expects.
Each is backed either by the GitHub documentation or by a measurement on a live repository.

| Trap | Symptom | Action |
|---|---|---|
| The wiki repository is not created by a push | `remote: Repository not found` | save the first page in the web interface, then publish |
| Wikis are barely indexed | a page exists, search never shows it | per documentation only wikis with 500+ stars and public editing disabled are indexed; use GitHub Pages |
| A private wiki needs a paid plan | no wiki in a private repository | it will not exist on the free plan |
| Flat namespace | a link to `docs/page` fails | every page lives in the wiki root |
| A relative image in a wiki | does not render | commit it, reference an absolute raw URL |
| `.md` in a wiki link | raw file or 404 | drop the extension |
| Cyrillic anchors | `#Установка` is not found | punctuation dropped, spaces to hyphens, lowercase |
| An em dash in a heading | a double hyphen in the anchor | the dash is removed; two spaces become two hyphens |
| `PUT /topics` replaces the list | topics you did not touch vanish | merge with the existing set, re-read |
| More than 20 topics | some topics disappear | the API stores 20 |
| Pages in a private repository | `422 Your current plan does not support GitHub Pages for this repository` | not available on the free plan |
| Pages builds are asynchronous | 404 right after enabling | poll the build, then the URL |
| `gh api --jq .content` | base64 with line breaks | `-H 'Accept: application/vnd.github.raw'` |
| An SVG as a social preview | the upload is rejected | PNG, JPG or GIF only |
| The platform's own anchor example | a capital Greek letter against a lowercase rule | compare anchors case-insensitively |

## Three traps that cost the most

### A wiki does not replace a website

The GitHub documentation states it plainly: only wikis with 500+ stars and public editing disabled
are indexed, and if indexing is what you need, use GitHub Pages. So "write a wiki and we will be
found" is a wrong strategy: a wiki serves the people who already reached the repository.

### `--prune` deletes foreign work

Publication keeps pages the build does not contain and prints their list. Deletion is a separate
flag. The reason is simple: the server may hold pages written by hand, and losing them silently is
not acceptable.

### A check that examined zero objects

An empty tree, a broken path, a missing file — none of these produce a green result. They produce
an error or a `coverage.skipped` line. Otherwise an agent reports success having checked nothing,
which is worse than a failure.

## Checking the traps yourself

```bash
python tools/ghagent.py doc --root . --json
python tools/ghagent.py audit --repo owner/name
python tools/ghagent.py assets check
python tools/ghagent.py wiki verify
```

`doc --json` carries a `rules_examined` field: it shows how many objects each rule examined. A
zero there means the rule did not run, not that it passed.

## Next

- [Import into another agent](07-Import).
- [File contracts](03-Repository-Contract).
