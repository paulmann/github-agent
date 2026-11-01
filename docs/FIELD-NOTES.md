# Field notes

What real repositories taught the pack. Every entry is a defect that was reported by someone
who ran the tool on work that was already correct — the most expensive kind, because the only
way to keep a gate green was to switch off the check that was right.

The reports are anonymised on purpose: what matters is the shape of the tree, not whose tree it
was. Each entry names the rule that changed and the test that now holds it.

| # | Symptom | Rule | Now |
|---|---|---|---|
| 1 | `wiki verify --wiki-dir <clone>` verified a directory nobody passed | `wiki.not-applicable` | the named checkout is verified, and the header says which directory |
| 2 | every wiki link reported as a missing file | `md.link-local` | page names resolve inside a wiki checkout |
| 3 | `_Sidebar.md` and `_Footer.md` demanded an H1 | `md.h1` | wiki partials are a note |
| 4 | agent scratch directories produced privacy errors | `privacy.abs-path` | the walk skips dot-directories except `.github/` |
| 5 | a banner silently lost half its title | `assets.truncated` | a cut title or tagline is a warning |
| 6 | a legal `## [Unreleased]` failed the changelog gate | `changelog.link-refs` | optional link references are a warning |
| 7 | a grouped heading `### Added — detail` was "unknown" | `changelog.types` | the subtitle is dropped before the lookup |
| 8 | a version told in prose was "empty" | `changelog.prose-version` | a warning; only a version with nothing stays an error |
| 9 | `meta check --repo` reported an empty description that was not empty | `meta.remote` | the remote is read; an unreadable remote is an error |
| 10 | a repository without a local wiki lost three points | `wiki.source-absent` | the item is skipped, not failed |

## 1. `wiki verify` ignored the directory it was given

**Symptom.** A repository keeps its wiki in its own git repository, as GitHub does by default
once the wiki has more than one page. `ghagent wiki verify --root <repo> --wiki-dir <clone>`
answered `[ERROR] wiki.build-missing — no built wiki at <repo>/.ghagent/wiki`, and the header of
that report named the directory the caller never passed.

**Cause.** `verify` was given the build directory only; the command computed it from `--root`
and the flag was consumed by `build`/`publish` alone.

**Now.** `verify_target()` decides in the documented order: an explicit `--out`, then a
`--wiki-dir` that already looks like a wiki (`Home.md`, `_Sidebar.md` or `_Footer.md` present),
then the build. A repository with neither sources nor a build gets one note, `wiki.not-applicable`,
and exit `0`: nothing is missing, so nothing can fail.

## 2 and 3. A wiki addresses pages by name

**Symptom.** `ghagent doc --root <wiki checkout>` on a 24-page wiki: 121 errors, of which 117
were correct links (`[Architecture](Architecture)`) reported as missing files, and 2 were the
navigation partials without an H1. The only way to run the gate was
`--ignore md.link-local,md.h1` — which also switched off the checks that find real breakage.

**Cause.** The link rule resolved a target against the file system and nothing else. On GitHub a
wiki resolves `Page` to `Page.md`; in an ordinary repository the very same link is a 404, so a
blanket resolution would have created false passes everywhere else. `wiki verify` already spoke
the wiki namespace; `doc` did not — one tool, two opinions about one tree.

**Now.** The wiki context is detected from the tree: a directory that carries `_Sidebar.md` or
`_Footer.md` is a wiki checkout, and the configured `wiki/` directory is wiki sources even without
the generated sidebar. There a page name resolves to `Page.md` (the suffix is appended, not
substituted, so `Migration-3.x-to-4.0` keeps its dots). Everywhere else the link stays a 404.
`_Sidebar.md`, `_Footer.md` and `_Header.md` are furniture: the H1 rule reports them as a note. A
link to a page that does not exist is still an error.

Measured after the fix: 121 errors → 0 errors on the same checkout, and `doc --include-wiki` on a
repository whose wiki sources were checked as ordinary files went from 43 errors to 0. The
repository that has no wiki at all still fails on a broken link.

## 4. Tool state is not documentation

**Symptom.** Six `privacy.abs-path` errors in files such as `.swarm/00-MISSION.md` and
`.zwork/notes.md` — the scratch space of a coding agent, never published, containing the paths
of the machine it ran on. The gate was red for a plan file.

**Cause.** The walker had a list of excluded *names* (`node_modules`, `.git`, `.idea`…). Every
new agent invents a new dot-directory, so the list was always one name behind.

**Now.** The rule is structural: a directory whose name starts with a dot is tool state, except
`.github/` and `.well-known/`, which are published surfaces. `iterate_text_files` is the single
walker for `doc` and `privacy`, so both commands see the same tree — and `doc` now also honours
`ignore_rules` from `.ghagent.json`, which `audit` had been honouring alone.

## 5. A banner that silently cut its own title

**Symptom.** `assets render --write` with no flags produced a card whose title ended in an
ellipsis and whose tagline stopped mid-sentence. Nothing said so; the image looked intentional.

**Cause.** Two defects, one visible. The wrapper stopped after `max_lines - 1` lines, so a
38-character title was marked as cut although two lines had room for it; and the chip row was
built from the top three languages *by file count*, so a PHP library whose tooling happened to
be Python and shell advertised `php python shell`.

**Now.** The last line is filled before anything is dropped; a genuinely cut title or tagline is
a warning that names the limit; chips come from the declared keywords, with languages only as a
fallback; emoji from an H1 are stripped (the font set has no colour glyphs); and an empty command
line is reported as a note rather than left as a hole in the card.

## 6 and 7. Two findings that turned a correct changelog red

**Symptom.** A changelog that follows Keep a Changelog 2.0.0 failed the gate: `changelog.link-refs`
because `## [Unreleased]` had no bottom-of-file `[unreleased]:` line, and ten `changelog.types`
warnings for headings such as `### Added — template language`.

**Cause.** The link references are *optional* in Keep a Changelog and were treated as required;
the type lookup compared the whole heading with the six canonical names, so a grouping subtitle
made a known type unknown.

**Now.** Missing link references are a warning with the reason attached; a heading is reduced to
its type before the lookup (`Added — template language` is `Added`, and section order still works).
Measured on that changelog: 10 warnings → 2, and both remaining ones are real.

## 8. A release told in prose

**Symptom.** `changelog.empty-version` for a historical release described in a paragraph instead
of `### Added` subsections. The document was complete; the reader could understand it.

**Cause.** The rule counted only list items, so a section with prose had zero items and was
reported as empty in two different ways.

**Now.** A version with prose is `changelog.prose-version` (warning) and says why subsections are
still better: they can be compared and released by machine. A version with no content at all
remains `changelog.empty-version` (error), so the relaxation cannot hide an unfinished entry.

## 9. `meta check --repo` never read the remote

**Symptom.** `ghagent meta check --repo owner/name` answered `[ERROR] meta.empty — description is
empty` and `0 topic(s)` for a repository whose description and twenty topics were visible on
GitHub.

**Cause.** `--repo` was accepted by the parser and ignored by the command: it validated the empty
arguments it had been given by nobody.

**Now.** The remote is read through `gh api`. If it cannot be read, the finding is `meta.remote`
("cannot read … through gh api"), not a claim about an empty field — a missing answer is not an
empty answer.

## 10. A repository that keeps its wiki elsewhere is not deficient

**Symptom.** `wiki-source — no wiki source directory` as a failed audit item, three points lost,
for a repository whose wiki simply lives in its own repository.

**Cause.** The audit treated "this pack keeps `wiki/` in the tree" as a universal contract.

**Now.** The item is `skipped` and therefore outside the score, with a note that explains where a
separate wiki is checked instead. Measured effect on that repository: 82.7% → 84.3%, with
`wiki-source` counted as `skipped` rather than `fail`.

## What this changed about the pack itself

- The rules table in [Rules](RULES.md) is the single index: every entry above has a rule id there.
- Seven new fixtures in `tests/run_tests.py` lock the behaviour: wiki mode, hidden directories,
  changelog traps, the verify target, the unreadable remote, the cut banner.
- `doc` and `privacy` share one walker, and `doc` reads `ignore_rules`, so the two commands can no
  longer disagree about the same tree.

The general lesson is worth stating once: a checker is only trusted while it is green on work
that is already correct. The moment the response to a finding is `--ignore`, the rule is dead —
and the next real defect walks through the hole it left.
