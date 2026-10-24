<!-- ghagent: template -->
# <Project name>

**<One sentence: what it is, for whom, what it does differently. No superlatives.>**

[![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/<owner>/<repo>?label=release&sort=semver)](https://github.com/<owner>/<repo>/releases)
[![License](https://img.shields.io/badge/license-<SPDX>-blue.svg)](LICENSE)
[![Runtime](https://img.shields.io/badge/<runtime>-<version>-informational)](<link to runtime>)

<img src="https://github.com/<owner>/<repo>/raw/main/assets/social-preview.png"
     alt="<Project name> — <what it does>"
     width="100%">

[**Quick start**](#quick-start) · [**Documentation**](#documentation) · [**Wiki**](https://github.com/<owner>/<repo>/wiki) · [**AGENTS.md**](AGENTS.md) · [**Changelog**](CHANGELOG.md) · [**Русская версия**](README.ru.md)

> **Documentation status.** Numbers below were measured on <YYYY-MM-DD> against version <x.y.z>.
> Long guides live in the [Wiki](https://github.com/<owner>/<repo>/wiki) and `docs/`.

<Owner name> is not affiliated with <third-party trademark>, if the project mentions one.

## Contents

- [What it is](#what-it-is)
- [In numbers](#in-numbers)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Documentation](#documentation)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## What it is

<Three to six bullets: the concrete jobs the project does. Each names a capability a reader can
verify, not an adjective.>

| Decision | Why |
|---|---|
| <technical choice> | <the constraint it removes> |

## In numbers

Measured on <YYYY-MM-DD> against the published tree of <x.y.z>:

| Surface | Value | Measurement source |
|---|---:|---|
| <Files / lines> | <number> | `<command or path>` |
| <Tests> | <number> | `<command>` |
| <Runtime dependencies> | <number> | `<manifest>` |

## Installation

### Requirements

| Component | Requirement |
|---|---|
| <runtime> | <version> |
| <database> | <version> |
| <what is not needed> | **not required** |

### From source

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
<install command>
<verify command>
```

### Checking the first result

```bash
<command>
# expected: <one line of real output>
```

## Usage

```bash
<the three commands a new user runs first>
```

| Task | Command | Result |
|---|---|---|
| <task> | `<command>` | <observable result> |

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `<NAME>` | <what it changes> | `<default>` |

## Limitations

- <what the project deliberately does not do>;
- <what fails, and how it fails loudly>;
- <what needs a paid plan or an external service>.

## Documentation

| Document | Content |
|---|---|
| [Wiki](https://github.com/<owner>/<repo>/wiki) | <long guides> |
| [`docs/ARCHITECTURE.md`](<docs/ARCHITECTURE.md>) | <how it is built> |
| [`AGENTS.md`](<AGENTS.md>) | <instructions for coding agents> |
| [CHANGELOG.md](<CHANGELOG.md>) | <version history> |

## Development

```bash
<lint command>
<test command>
<build command>
```

Tests need no network. New behaviour arrives with a test; a new check arrives with a fixture.

## Contributing

Before a pull request: <commands>. Rules: [CONTRIBUTING.md](<CONTRIBUTING.md>), security:
[SECURITY.md](<SECURITY.md>), support: [SUPPORT.md](<SUPPORT.md>).

## License

[<SPDX>](LICENSE).
