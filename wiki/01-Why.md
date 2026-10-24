# Why this exists

A repository rarely fails on code. It fails on documentation: `git push` succeeds, the tests are
green, and a reader cannot find out how to start. The defect lives for years because nothing
reports it — neither the compiler nor CI.

## Five defects that appear most often

| Defect | How it looks | Why it hurts |
|---|---|---|
| A README with no installation | architecture and philosophy first | the reader leaves at the second paragraph |
| A changelog with no dates | `## 1.1.0` and nothing else | versions cannot be compared or linked |
| A wiki with no navigation | ten pages, no links | the pages exist and cannot be found |
| A link to nowhere | `[API](docs/api.md)` when the file is `docs/API.md` | documentation "exists" and does not open |
| A three-word description | "panel", "tools" | search never shows the project |
| A repository with no picture | an empty link card | it reads as abandoned |

None of these is caught by running the code. All of them are caught by comparison: a file against
a contract, a link against the tree, an anchor against a heading.

## Why this is a job for an agent

The checks are mechanical, but they need attention to details a human does not hold in mind:
sixteen required files, anchor rules with Cyrillic, the order of change types, the twenty-topic
limit in the API, the 1280×640 rule for a social preview. An agent with one command does this in
seconds and does not forget the exceptions.

The other side of that coin: an agent without checks invents. It writes "fast panel" instead of a
measured number, and "see the documentation" instead of a link. That is why the pack is built so
that every claim is either verified or rejected.

## What counts as failure

| Situation | Why it is a failure |
|---|---|
| A check examined zero files and returned success | the green result means nothing |
| A link to a wiki page that does not exist | the reader believes the documentation exists |
| A wiki publication deleted a foreign page | data loss without a warning |
| A release with no entries | the changelog stops meaning anything |
| A number in the README with no source | it cannot be verified, so it cannot be trusted |

## Next

- [Installation](02-Install) — install and verify.
- [Platform traps](06-Traps) — where GitHub behaves unexpectedly.
- [File contracts](03-Repository-Contract) — what exactly is checked.
