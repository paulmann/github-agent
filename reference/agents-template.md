<!-- ghagent: template -->
# AGENTS.md — <what an agent may do here>

One page from which an agent learns how to install the project, how to prove the work is done,
and what not to touch. Written to be read before the first command, not after the first error.

## Contents

- [What it is](#what-it-is)
- [Quick start](#quick-start)
- [Checks](#checks)
- [Rules](#rules)
- [Traps](#traps)
- [Do not](#do-not)

## What it is

<Two or three sentences: the purpose of the project and what exactly is automated here.>

## Quick start

```bash
<clone>
<install>
<verify>
```

The last command must print `<one line>` and exit `0`.

## Checks

| What | Command | Expectation |
|---|---|---|
| <tests> | `<command>` | exit 0 |
| <lint> | `<command>` | exit 0 |
| <contract> | `<command>` | exit 0 |

A check that examined zero objects counts as failed: an empty result is not "all good".

## Rules

1. <A rule with a verifiable consequence, not a wish.>
2. Numbers are measured only: a command or a file, named.
3. No secrets in the repository: values become `<placeholder>`.
4. Text files are UTF-8 without BOM, LF line endings.
5. <The project's branching and commit rule.>

## Traps

| Trap | Symptom | Action |
|---|---|---|
| <trap> | <how it is noticed> | <the fix> |

## Do not

- <prohibition and its reason>;
- <prohibition and its reason>.

## Layout

```text
<dir>/    <purpose>
<file>    <purpose>
```
