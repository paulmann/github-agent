# syntax=docker/dockerfile:1

# Build the wheel from the build context, then install it into a clean runtime image.
# No PyPI copy of github-agent is needed: the context is the source of truth.
FROM python:3.13-slim AS build

WORKDIR /src

RUN python -m pip install --no-cache-dir --disable-pip-version-check --upgrade pip

COPY pyproject.toml README.md LICENSE ./
COPY tools ./tools

RUN python -m pip wheel --no-cache-dir --disable-pip-version-check --wheel-dir /wheels /src


FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="github-agent" \
      org.opencontainers.image.description="Repository and wiki steward: one command per documentation job, standard library only." \
      org.opencontainers.image.source="https://github.com/paulmann/github-agent" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m pip install --no-cache-dir --upgrade pip

COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links /wheels github-agent-cli \
    && rm -rf /wheels

# The repository under test is mounted here.
WORKDIR /repo

ENTRYPOINT ["ghagent"]
CMD ["--help"]
