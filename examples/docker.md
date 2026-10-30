# Running github-agent in Docker

The repository ships a `Dockerfile` that builds the wheel from the build context and installs it
into a clean runtime image. No published copy of `github-agent` is needed: the checked-out source
is the source of truth. No registry image is published as part of 1.2.0, and CI does not build
the container, so the tag below is a local convention.

## Build

From the root of the github-agent checkout:

```bash
docker build -t ghagent .
```

The build needs network access for the `python:3.13-slim` base image and the build backend; the
application itself is installed from the local context. The image is multi-stage: the build stage
produces a wheel, the runtime stage installs it and nothing else.

## Run against a repository

The image working directory is `/repo` and the entry point is `ghagent`, so mount the repository
under test there and pass the command as arguments:

```bash
cd /path/to/your/repository
docker run --rm -v "$PWD:/repo" ghagent audit .
```

On Windows PowerShell the mount path is quoted differently, but the target stays `/repo`:

```powershell
docker run --rm -v "${PWD}:/repo" ghagent audit .
```

Other commands take the same shape:

```bash
docker run --rm -v "$PWD:/repo" ghagent doc --root .
docker run --rm -v "$PWD:/repo" ghagent privacy --root .
docker run --rm -v "$PWD:/repo" ghagent changelog check
```

Read-only mounts are enough for every check. `ghagent audit .` returns `0` clean, `1` findings at
error level, `2` a usage or environment problem, and the container exits with the same code, so
it can be used in a scripted gate:

```bash
docker run --rm -v "$PWD:/repo" ghagent audit . --min-score 80
```

## The self-test suite is not in the image

The wheel ships the CLI only; `tests/` and the skill templates stay in the repository. `ghagent
selftest` and `ghagent install` therefore exit `2` in the container, with a message that points at
the git clone. Install the skill into an agent from a checkout, not from the image.

## PNG rendering

The runtime image installs the base package, so `assets render` writes the SVG. PNG output needs
the optional Pillow extra; build a derived image when you need it:

```dockerfile
FROM ghagent
RUN python -m pip install --no-cache-dir pillow
```

Then run the same commands. See [README.md](../README.md#images) for what the two formats are.
