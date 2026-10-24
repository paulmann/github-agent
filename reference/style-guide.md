# Documentation style on GitHub

The rules the pack enforces. Each is backed either by the GitHub documentation or by a
measurement on a live repository — the source is named next to it.

## What GitHub actually renders

| Construct | Support | Note |
|---|---|---|
| Headings `#` … `######` | yes | one `H1` per document; levels are not skipped |
| Tables with `\|` | yes | every row must have the same cell count as the header |
| Escaped `\|` inside a cell | yes | without escaping the cell is split |
| Inline code with a pipe: `` `a \| b` `` | yes | backticks protect it |
| Fenced code with a language | yes | no language means no highlighting, and the linter warns |
| `> [!NOTE]` … `> [!CAUTION]` | yes, exactly five types | `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION` |
| Footnotes `[^1]` | yes | rendered at the bottom regardless of where they are declared |
| Task lists `- [ ]` | yes | README and issues |
| `<details><summary>` | yes | collapsed blocks for long logs |
| Math `$…$`, `$$…$$` | yes | also in wikis |
| Mermaid | yes | ` ```mermaid `; supported in wikis |
| A relative image inside a wiki | **no** | the wiki is a separate repository |
| An auto-generated table of contents in the text | **no** | readers get the Outline panel; nothing is inserted into the file |
| Nested wiki pages | **no** | the namespace is flat |

## Heading anchors

GitHub's documented rules: letters are lowercased; spaces become hyphens; any other whitespace
and punctuation is removed; leading and trailing whitespace is stripped; markup is removed;
a repeated heading gets `-1`, `-2`.

Consequences that break links most often:

- `## Ship it — fast, safely` → `#ship-it--fast-safely`: the em dash is removed, and the two
  surrounding spaces produce **two** hyphens;
- Cyrillic survives: `#установка`, never transliterated;
- `## API and MCP` → `#api-and-mcp`.

Measurement and one caveat: the platform's own documentation shows an anchor with a capital
Greek letter (`…#letter-Θ`), which contradicts its lowercase rule. `ghagent` therefore compares
anchors case-insensitively — otherwise it would report a false `FAIL` on the platform's own
document.

## Tone and content

- Write what a reader can verify: a command, a file, a number, an API response.
- No judgement without a unit: "fast" does not replace "0.4 s for 10,000 lines".
- Every number in a numbers table carries its source: a command or a path.
- One thought per sentence, one fact per bullet, paragraphs under five lines.
- No emoji in metadata, headings or repository descriptions: search and parsers read them.
- No superlatives ("blazing fast", "best-in-class"): they cannot be verified.

## README layout

1. `H1` — the project name, under 60 characters.
2. A paragraph: what it is, for whom, what it does differently.
3. A banner image or a badge block. 3–8 badges: CI, release, license, runtime.
4. A table of contents from `H2` once the document passes 200 lines.
5. Installation → quick start → configuration → capabilities → limitations → documentation →
   development → contributing → license. The order may vary; the set may not.

## Wiki page layout

1. `H1` — the page name (the filename without `.md`).
2. One paragraph: why this page exists.
3. A table of contents from `H2` when there are more than five sections.
4. Links to neighbouring pages — without `.md`.
5. At the end, a link to the repository or the next page: a reader must not hit a dead end.

## Defects the pack treats as blocking

| Defect | Rule |
|---|---|
| BOM, CRLF, missing final newline | `doc.bom`, `doc.crlf`, `doc.final-newline` |
| A second `H1`, a skipped heading level | `md.h1`, `md.heading-skip` |
| An unclosed code fence | `md.fence` |
| A table row with a different cell count | `md.table` |
| A link to a missing file or anchor | `md.link-local`, `md.link-anchor` |
| A table of contents pointing at a heading that does not exist | `md.toc` |
| A token, private key or absolute machine path | `privacy.secret`, `privacy.abs-path` |
| An image over plain `http://` | `md.image-http` |
| A social preview that is not PNG/JPG/GIF, or over 1 MB, or under 640×320 | `assets.social-*` |
