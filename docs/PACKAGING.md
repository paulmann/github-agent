# Packaging and distribution

How `github-agent` is built, installed, published and consumed. The project has one runtime
contract that the packaging exists to protect: **zero third-party dependencies**. The wheel is
the CLI plus its library, the sdist is the complete pack, and the CLI itself proves both.

Measured with CPython 3.14.7 and `pip` 26.2.1 on the tree at version 1.2.0. Commands are
written for a POSIX shell; the PowerShell equivalents are in
[scripts/build_and_check.ps1](../scripts/build_and_check.ps1).

## Contents

- [What ships](#what-ships)
- [One version, one source](#one-version-one-source)
- [Build locally](#build-locally)
- [Automated build check](#automated-build-check)
- [Install](#install)
- [From source](#from-source)
- [Wheel and sdist contents](#wheel-and-sdist-contents)
- [GitHub Action](#github-action)
- [Docker image](#docker-image)
- [pre-commit hooks](#pre-commit-hooks)
- [Release procedure](#release-procedure)
- [PyPI Trusted Publishing](#pypi-trusted-publishing)
- [Deferred: Homebrew and Scoop](#deferred-homebrew-and-scoop)
- [Deferred: mypy and ruff](#deferred-mypy-and-ruff)
- [Failure modes](#failure-modes)

## What ships

| Artefact | Built from | Contains | Audience |
|---|---|---|---|
| Wheel `github_agent-1.2.0-py3-none-any.whl` | [pyproject.toml](../pyproject.toml) | `ghagent.py`, `ghalib/`, dist-info | `pip`, `uv`, `pipx` users |
| sdist `github_agent-1.2.0.tar.gz` | the same tree | the whole pack: `tools/`, `tests/`, `skills/`, `reference/`, `docs/`, `wiki/`, `assets/`, `.github/`, packaging files | pack installation, reproducible source |
| Composite Action [action.yml](../action.yml) | the tagged repository | installs the action checkout with `pip`, then runs `ghagent` | CI workflows |
| Container image [Dockerfile](../Dockerfile) | the build context | the wheel in `python:3.13-slim`, `ENTRYPOINT ghagent` | local containers |
| pre-commit hooks [.pre-commit-hooks.yaml](../.pre-commit-hooks.yaml) | the tagged repository | four hooks, `language: python` | contributors |

`requires-python` is `>=3.11`; CI runs the self-tests on 3.11 and 3.13. The only optional
dependency is the `png` extra (Pillow) and it changes one thing: PNG output of
`ghagent assets render`.

## One version, one source

`tools/ghalib/util.py` holds the only version literal in the tree:

```toml
[tool.hatch.version]
path = "tools/ghalib/util.py"
pattern = '^PACK_VERSION = "(?P<version>[^"]+)"'
```

`pyproject.toml` declares `dynamic = ["version"]` and never repeats the number. To release a
version, change `PACK_VERSION` once; the wheel filename, wheel metadata, the sdist name and
`ghagent --version` all follow. A captured mismatch is a packaging defect, so the build check
compares the artefact version against the file instead of trusting either side.

## Build locally

```bash
python -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Measured output of the last verified build:

```text
Successfully built github_agent-1.2.0.tar.gz and github_agent-1.2.0-py3-none-any.whl
...
Checking dist/github_agent-1.2.0-py3-none-any.whl: PASSED
Checking dist/github_agent-1.2.0.tar.gz: PASSED
```

`python -m build` uses build isolation: it downloads `hatchling>=1.27` (the declared build
backend) from PyPI. On a machine without network, install `hatchling` first and pass
`--no-isolation`. `dist/`, `build/` and virtual environments are in `.gitignore`; no build
output is committed.

The wheel is built from the sdist by `python -m build`, so a broken sdist cannot hide behind
a good wheel: the same file list that is published as source is the one that produces the
installed package.

## Automated build check

```bash
bash scripts/build_and_check.sh                     # Linux, macOS, WSL
pwsh -NoProfile -File scripts/build_and_check.ps1   # Windows
```

Both scripts create their own virtual environments under the system temporary directory and
remove them afterwards; they do not touch the working tree. Each run asserts, in order:

1. the sdist and the wheel build from this tree;
2. `twine check` accepts both;
3. the artefact version equals `PACK_VERSION`;
4. the wheel contains top-level `ghagent.py` and `ghalib/`, and no `tools/` package;
5. `Requires-Dist` holds nothing except the `png` extra;
6. a clean virtual environment installs the wheel, `ghagent --version` prints the expected
   string, and the installed CLI runs `doc` and `audit` against this checkout.

The same assertions run in the `package` job of [CI](../.github/workflows/ci.yml), so a pull
request that breaks packaging is red before it merges.

## Install

```bash
uv tool install github-agent            # isolated CLI, recommended
pipx install github-agent               # isolated CLI, alternative
pip install github-agent                # into the current environment
pip install "github-agent[png]"         # plus Pillow, for PNG banner output
ghagent --version                       # github-agent 1.2.0
```

These commands resolve from PyPI after the first publication; until then install the wheel
built in [Build locally](#build-locally) or use the source checkout below. The last verified
clean installation, measured in a fresh virtual environment:

```console
$ pip list
Package      Version
------------ -------
github-agent 1.2.0
pip          26.2.1
```

Nothing else is installed: the package has no runtime dependency, and the only `Requires-Dist`
line in the wheel metadata is `pillow>=10.0; extra == 'png'`.

`uv` and `pipx` were not installed in the verification environment, so those two commands are
documented client forms and were not executed here; the measured path is `pip install` of the
wheel and `pip install <repository directory>`, both of which produce the same console script.

The wheel ships the CLI only. `ghagent selftest` and the `install` family need the source tree
(`tests/`, `tools/`); from an installed copy they exit `2` and say so instead of pretending to
have verified anything. The next section is that path.

## From source

```bash
git clone https://github.com/paulmann/github-agent.git
cd github-agent
python tools/ghagent.py --version       # github-agent 1.2.0
python tools/ghagent.py selftest        # must print PASS
python tools/ghagent.py install --profile harness --write
```

Source mode is the only mode that can self-test the pack or copy it into an agent skill root:
the sdist is the same tree, so an unpacked sdist behaves the same way. An editable install
(`pip install -e .`) also resolves `ghagent` to `tools/ghagent.py`, so `ghagent selftest` keeps
working from an editable copy; a regular wheel installation cannot do either.

## Wheel and sdist contents

The wheel has 17 entries and no other top-level name:

| Path | Why |
|---|---|
| `ghagent.py` | the console-script target (`ghagent = "ghagent:main"`) |
| `ghalib/` | 11 library modules, one small file each, standard library only |
| `github_agent-1.2.0.dist-info/` | `METADATA`, `WHEEL`, `entry_points.txt`, `licenses/LICENSE`, `RECORD` |

`only-include` and `sources` in `pyproject.toml` strip the `tools/` prefix, so site-packages
gets `ghagent.py` and `ghalib/` and never a generic `tools` package. The verification checks
that absence explicitly.

Key metadata lines from `github_agent-1.2.0.dist-info/METADATA`:

```text
Metadata-Version: 2.5
Name: github-agent
Version: 1.2.0
Requires-Python: >=3.11
License-Expression: MIT
License-File: LICENSE
Provides-Extra: png
Requires-Dist: pillow>=10.0; extra == 'png'
```

The sdist carries the complete pack: all top-level documents and translations, `tools/`,
`tests/`, `skills/`, `reference/`, `docs/`, `wiki/`, `assets/`, `examples/`, `.github/`,
`scripts/`, `action.yml`, `Dockerfile`, `.dockerignore`, `.pre-commit-hooks.yaml` and
`pyproject.toml`. That is what `ghagent install` copies, so
`pip download --no-binary :all: github-agent` followed by an unpack and
`python tools/ghagent.py selftest` reproduces a verifiable pack.

## GitHub Action

```yaml
name: Repository hygiene
on: [push, pull_request]
permissions:
  contents: read
jobs:
  ghagent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: paulmann/github-agent@v1.2.0
        with:
          command: audit . --min-score 80
```

The action is `runs: using: composite`. It installs the checked-out action repository into the
runner's Python with `pip install "$GITHUB_ACTION_PATH"`, so it does not need a PyPI release
and works as soon as the tag exists. It uses `actions/setup-python@v5` and needs network only
for the build backend and Python.

| Input | Default | Effect |
|---|---|---|
| `command` | `audit . --min-score 80` | argument string passed to `ghagent` |
| `min-score` | `80` | appended when `command` runs `audit` without its own `--min-score` |
| `working-directory` | `.` | directory under the workspace to run in |
| `python-version` | `3.13` | Python used for the run |
| `github-token` | `${{ github.token }}` | exported as `GITHUB_TOKEN` for remote metadata calls |

The action declares no outputs. Its result is the step exit code: `0` clean, `1` findings,
`2` usage or environment problem. For a command other than `audit`, `command` is executed as
given.

## Docker image

```bash
docker build -t ghagent:1.2.0 .
docker run --rm ghagent:1.2.0 --version
docker run --rm -v "$PWD:/repo" ghagent:1.2.0 audit . --min-score 80
```

Two stages, both `python:3.13-slim`. The build stage runs `pip wheel` against the build
context (no PyPI copy of `github-agent`); the runtime stage installs that wheel with
`--no-index --find-links` and copies nothing else. The image sets `WORKDIR /repo`, so mounting
a repository at `/repo` needs no path argument, `ENTRYPOINT` is `ghagent`, and the default
command is `--help`.

Docker was not installed in the verification environment: the image was not built or run
here, and no registry image is published by this repository. Treat the commands above as the
supported local path, not as a public image reference.

## pre-commit hooks

```yaml
repos:
  - repo: https://github.com/paulmann/github-agent
    rev: v1.2.0
    hooks:
      - id: ghagent-doc
      - id: ghagent-audit
      - id: ghagent-privacy
      - id: ghagent-changelog
```

`rev` must be a released tag: `language: python` makes pre-commit build the wheel from the
tagged tree and expose the `ghagent` console script. All four hooks set `pass_filenames: false`
because each command examines a tree, not a list of changed files.

| Hook | Runs | Trigger |
|---|---|---|
| `ghagent-doc` | `ghagent doc --root .` | any markdown file changed (`types_or: [markdown]`) |
| `ghagent-audit` | `ghagent audit . --min-score 80` | every commit (`always_run`) |
| `ghagent-privacy` | `ghagent privacy --root .` | every commit (`always_run`) |
| `ghagent-changelog` | `ghagent changelog check` | `CHANGELOG.md` changed |

## Release procedure

1. Set `PACK_VERSION` in `tools/ghalib/util.py`; change nothing else for the version.
2. Add `## [X.Y.Z] - YYYY-MM-DD` to `CHANGELOG.md` and `CHANGELOG.ru.md`, update the link
   blocks in both, then run `python tools/ghagent.py changelog check`.
3. Run the six repository checks and the build check:
   `python tools/ghagent.py selftest`, `doc --root .`, `audit .`, `changelog check`,
   `assets check`, `privacy --root .`, then `bash scripts/build_and_check.sh`.
4. Commit on `main`, push, and watch CI until green; never tag a red commit.
5. Create an annotated tag, then a GitHub release whose notes come from
   `python tools/ghagent.py changelog notes X.Y.Z`; attach `dist/github_agent-X.Y.Z.tar.gz`,
   `dist/github_agent-X.Y.Z-py3-none-any.whl` and `SHA256SUMS.txt`.
6. Download the assets again and compare their SHA-256 values with `SHA256SUMS.txt`; publish
   only after the comparison matches.
7. Upload to PyPI deliberately, through the Publish workflow (next section), and verify the
   project page.
8. Optionally publish the wiki and refresh repository metadata; both are separate commands
   with their own verification.

The release assets are the durable artefact: PyPI forbids re-uploading the same version, so a
mistake is a new patch version, never a silently replaced file.

## PyPI Trusted Publishing

The `publish` workflow is manual (`workflow_dispatch`) because Trusted Publishing does not
exist for this repository yet. A `release: published` trigger added today would fail red: no
trusted publisher, no OIDC exchange, no upload. Set it up once:

1. On PyPI, add a **pending publisher** for the project `github-agent`: owner `paulmann`,
   repository `github-agent`, workflow `publish.yml`, environment `pypi`. A pending publisher
   removes the chicken-and-egg problem of publishing before the project exists.
2. In the GitHub repository, create the environment `pypi` (Settings, Environments) and
   optionally require a reviewer; the workflow declares `environment: pypi` and
   `id-token: write` and needs no password secret.
3. Run the workflow manually: `gh workflow run publish.yml -f confirm=publish`, or Actions,
   Publish, Run workflow, after typing `publish` in the confirmation input.
4. Verify the upload on `https://pypi.org/project/github-agent/` and with
   `pip index versions github-agent`.
5. Once that works, extend the trigger in [publish.yml](../.github/workflows/publish.yml) with
   `release: types: [published]` and remove the `if:` guard on the publish job, so a published
   release becomes the only publication event.

## Deferred: Homebrew and Scoop

A Homebrew formula and a Scoop manifest are deliberately **not** in this repository yet. Both
need a real, immutable download URL and a real SHA-256, and neither exists until the sdist is
on PyPI and a release has uploaded it. A formula written now would carry a placeholder hash,
which violates the project rule that every number names its source, and would install nothing
or the wrong bytes.

When the first PyPI release exists:

- a formula belongs in a separate tap repository, with `url` pointing at the PyPI sdist and
  `sha256` copied from `sha256sum dist/github_agent-X.Y.Z.tar.gz`;
- a Scoop manifest uses the release asset URL and its measured hash, with `checkver` and
  `autoupdate` reading the PyPI JSON API;
- both gain a bump procedure that recomputes the hash after every release.

There is no placeholder `sha256` value anywhere in this tree; adding one is a defect, not a
stub.

## Deferred: mypy and ruff

Neither mypy nor ruff is enabled in CI. The repository has no configuration for either, and
running their defaults against the current tree would fail on existing code rather than on
this change; a permanently red job teaches contributors to ignore CI. Add them in a separate
change that lands with an explicit configuration and a clean baseline, and put the check in
the `package` job only after that baseline exists. The packaging job stays green and
meaningful in the meantime.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `ghagent selftest` exits `2` after `pip install` | the wheel ships the CLI only | clone the repository or unpack the sdist |
| `python -m build` fails without network | build isolation downloads `hatchling` | install `hatchling` and pass `--no-isolation` |
| wheel contains `tools/` | `sources`/`only-include` lost from `pyproject.toml` | restore them; the build check fails on the layout |
| version in the filename is stale | `PACK_VERSION` was not changed | change it in `tools/ghalib/util.py` only |
| `twine check` warns about metadata | an invalid license or readme declaration | keep `license = "MIT"` and `license-files = ["LICENSE"]` |
| the Action cannot find `ghagent` | `pip install "$GITHUB_ACTION_PATH"` did not run | check the composite step order and its exit code |
| pre-commit cannot find the revision | `rev` is a branch or a missing tag | use a released tag such as `v1.2.0` |
| a publish run fails on permissions | Trusted Publishing not configured, or no `pypi` environment | complete the setup above before uploading |
