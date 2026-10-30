# Using github-agent in GitHub Actions

The repository ships a composite action at [action.yml](https://github.com/paulmann/github-agent/blob/main/action.yml).
It installs the pack from its own checkout, so it does not wait for a PyPI release: the ref you
pin is the code that runs. Pin a release tag, never a branch.

## A complete workflow

```yaml
name: Repository hygiene

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  audit:
    name: Audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Score the repository
        uses: paulmann/github-agent@v1.2.0
        with:
          command: audit .
          min-score: "80"

  documents:
    name: Documents
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Markdown, links, anchors, tables
        uses: paulmann/github-agent@v1.2.0
        with:
          command: doc --root .
```

The step exit code is the result: `0` clean, `1` findings at error level (printed as `file:line`
with a rule id), `2` a usage or environment problem. GitHub fails the job on `1` and `2`, which
is the intended behaviour.

## Inputs

| Input | Default | Notes |
|---|---|---|
| `command` | `audit . --min-score 80` | any `ghagent` command without the program name |
| `min-score` | `80` | applied only when `command` starts with `audit` and passes no `--min-score` |
| `working-directory` | `.` | relative to `$GITHUB_WORKSPACE` |
| `python-version` | `3.13` | passed to `actions/setup-python@v5` |
| `github-token` | the workflow token | exported as `GITHUB_TOKEN` |

For a command that talks to the API, such as `audit --repo owner/name`, pass a token with the
scope the command needs:

```yaml
      - name: Audit GitHub metadata
        uses: paulmann/github-agent@v1.2.0
        with:
          command: audit --repo ${{ github.repository }} --http
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## One job, several checks

A single step can run one command only. To run the full set, use one step per command or a
`run:` block after installing the tool yourself:

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - run: pip install github-agent
      - run: ghagent doc --root .
      - run: ghagent audit . --min-score 80
      - run: ghagent privacy --root .
      - run: ghagent changelog check
```

## Docker instead of the action

If your runner can build containers but should not install Python packages, build the image
from a checkout of this repository and run it against the workspace. The image working directory
is `/repo`, so the repository under test is mounted there:

```yaml
      - uses: actions/checkout@v4
        with:
          path: workspace

      - uses: actions/checkout@v4
        with:
          repository: paulmann/github-agent
          ref: v1.2.0
          path: ghagent-src

      - name: Build the image
        run: docker build -t ghagent ./ghagent-src

      - name: Audit the workspace
        run: docker run --rm -v "$PWD/workspace:/repo" ghagent audit .
```

No registry image is published as part of 1.2.0; the build step is deliberate. See
[docker.md](docker.md) for the local commands and the mount rules.
