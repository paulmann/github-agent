---
name: repo-images
description: Choosing, rendering and placing the pictures a repository needs — a 1280x640 social preview, a README banner, a diagram, a screenshot — with the platform limits that decide whether an image is usable. Load when a repository has no picture, when link cards look empty, when an image fails to render in a wiki, or when a social preview is rejected.
---

# Images for a repository

A repository with no picture reads as abandoned. The social preview is what every link card in
chat, mail and search shows; the banner is the first thing a visitor sees. Both are cheap to
produce and easy to break, so the pack renders them from the project's own metadata and then
verifies them.

## What the platform accepts

Verified against GitHub's documentation, "Customizing your repository's social media preview":

| Property | Value |
|---|---|
| Formats | PNG, JPG or GIF |
| Size on disk | under 1 MB |
| Minimum pixels | 640×320 |
| Best rendering | 1280×640 |
| Transparency | PNG with transparency is supported |
| Where it is set | Settings → Social preview → Edit → Upload an image |

An SVG is fine inside a README — GitHub renders it — but it **cannot** be uploaded as a social
preview. That is why the pack writes both: `social-preview.png` for the upload and
`social-preview.svg` as a vector twin that needs no dependencies.

## Render

```bash
python <pack>/tools/ghagent.py assets render --eyebrow "REPOSITORY STEWARD" \
    --summary "What it does, for whom, in one sentence." \
    --tagline "The benefit, one line." \
    --command "project --help" --output "usage: project [-h]" --write
python <pack>/tools/ghagent.py assets check
```

| Flag | Effect |
|---|---|
| `--title` | the monospace wordmark; defaults to the README `H1` |
| `--eyebrow` | the small accent line above the wordmark |
| `--summary` | the bold statement; defaults to the README summary paragraph |
| `--tagline` | the muted line; defaults to the manifest description |
| `--command` | the command in the terminal panel; defaults to the manifest console script |
| `--output`, `--output-line` | terminal output lines; only these are drawn |
| `--fact LABEL=VALUE` | a fact pill, drawn value-first (`"MCP tools=40"` becomes `40 MCP tools`); at most six |
| `--facts auto` | the default without `--fact`: only facts the tree measures (version, license, dependencies, tests, wiki and doc pages, languages) |
| `--license` | SPDX id for the license pill |
| `--footer-left`, `--footer-right`, `--url`, `--homepage` | footer slots; the right one gets a green status dot |
| `--accent` | accent colour as `#rrggbb` |
| `--chips` | text-only pills; kept for older callers |
| `--size` | `WxH`, default `1280x640` |
| `--write` | actually write files; without it the command is a dry run |

The card is a dark vertical gradient with the wordmark, the summary, the tagline, the pill row, a
terminal panel with traffic lights, and the footer. One layout feeds both renderers, so the SVG is a
faithful twin of the PNG. Output goes to `assets/social-preview.svg` always, and
`assets/social-preview.png` when Pillow is installed. Without Pillow the report says so instead of
pretending a preview is ready. A fact the tree cannot measure is omitted, never invented.

## Place it

```markdown
<img src="https://github.com/<owner>/<repo>/raw/main/assets/social-preview.png"
     alt="<Project> — <what it does>" width="100%">
```

Rules the checker enforces:

1. the README references at least one image (`assets.readme-banner`);
2. every referenced file exists (`assets.missing-file`);
3. every image has alt text (`assets.alt`, `md.image-alt`);
4. no image is loaded over plain `http://` (`md.image-http`);
5. the preview is PNG/JPG/GIF (`assets.svg-social`), under 1 MB (`assets.social-size`) and at
   least 640×320, ideally 1280×640 (`assets.social-dimensions`).

## What else a repository needs

`assets suggest` lists the image kinds worth having, based on the tree:

| Kind | When | Note |
|---|---|---|
| banner / social preview | always | the only one that can be generated without decisions |
| diagram | the project has code with structure | prefer a Mermaid block: it stays editable and diffs cleanly |
| screenshot | the project has a UI | 1440 px wide, personal data removed, dark and light if both themes exist |
| terminal capture | the project has a CLI | use a code block, not an image: it stays searchable |

## Traps

| Trap | Symptom | Action |
|---|---|---|
| An SVG offered as a social preview | the upload is rejected or the card is blank | render a PNG |
| A relative image inside a wiki | does not render | the wiki cannot see the repository tree: absolute raw URL |
| The file is committed but the card is empty | the preview is set only in Settings | upload it once; the repository copy is not used automatically |
| Over 1 MB | the upload fails | let Pillow compress; it writes an optimised PNG |
| A screenshot with real data | a privacy leak with a long life | blur or synthetic data, then run `privacy` |
| Text baked into a screenshot | unsearchable, untranslatable | keep text in the markdown, the image shows only the picture |

## Done means

- `assets check` exits `0`.
- The README shows the banner, and the alt text says what the picture is.
- The social preview file is 1280×640 and under 1 MB, and has been uploaded in Settings.
- Any diagram in the README is a Mermaid block unless it cannot be.
