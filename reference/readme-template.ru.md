<!-- ghagent: template -->
# <Project name>

**<One sentence: what it is, for whom, what it does differently. No superlatives.>**

[![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/<owner>/<repo>?label=release&sort=semver)](https://github.com/<owner>/<repo>/releases)
[![License](https://img.shields.io/badge/license-<SPDX>-blue.svg)](LICENSE)
[![Runtime](https://img.shields.io/badge/<runtime>-<version>-informational)](<link to runtime>)

> **Status.** Numbers below were measured on <YYYY-MM-DD> against version <x.y.z>.
> Long guides live in the [Wiki](https://github.com/<owner>/<repo>/wiki) and `docs/`.

<Owner name> is not affiliated with <third-party trademark>, if the project mentions one.

## Содержание

- [Что это и зачем](#что-это-и-зачем)
- [В цифрах](#в-цифрах)
- [Installation](#installation)
- [Usage](#usage)
- [Настройка](#настройка)
- [Ограничения](#ограничения)
- [Документация](#документация)
- [Разработка](#разработка)
- [Участие в проекте](#участие-в-проекте)
- [License](#license)

## Что это и зачем

<Three to six bullets: the concrete jobs the project does. Each bullet names a capability a
reader can verify, not an adjective.>

| Решение | Почему |
|---|---|
| <technical choice> | <the constraint it removes> |

## В цифрах

Измерено <YYYY-MM-DD> по опубликованному дереву <x.y.z>:

| Поверхность | Значение | Источник измерения |
|---|---:|---|
| <Файлы / строки> | <число> | `<command or path>` |
| <Автотесты> | <число> | `<command>` |
| <Runtime-зависимости> | <число> | `<manifest>` |

## Installation

### Требования

| Компонент | Требование |
|---|---|
| <runtime> | <version> |
| <database> | <version> |
| <what is not needed> | **не требуется** |

### Из исходников

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
<install command>
<verify command>
```

### Проверка первого результата

```bash
<command>
# expected: <one line of real output>
```

## Usage

```bash
<the three commands a new user runs first>
```

| Задача | Команда | Результат |
|---|---|---|
| <task> | `<command>` | <observable result> |

## Настройка

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `<NAME>` | <what it changes> | `<default>` |

## Ограничения

- <what the project deliberately does not do>;
- <what fails and how it fails loudly>;
- <what needs a paid plan or an external service>.

## Документация

| Документ | Содержание |
|---|---|
| [Wiki](https://github.com/<owner>/<repo>/wiki) | <long guides> |
| [`docs/ARCHITECTURE.md`](<docs/ARCHITECTURE.md>) | <how it is built> |
| [`AGENTS.md`](<AGENTS.md>) | <instructions for coding agents> |
| [CHANGELOG.md](<CHANGELOG.md>) | <version history> |

## Разработка

```bash
<lint command>
<test command>
<build command>
```

Тесты не требуют сети. Новое поведение приходит с тестом; новая проверка — с фикстурой.

## Участие в проекте

Перед pull request: <commands>. Правила — [CONTRIBUTING.md](<CONTRIBUTING.md>),
безопасность — [SECURITY.md](<SECURITY.md>), поддержка — [SUPPORT.md](<SUPPORT.md>).

## License

[<SPDX>](LICENSE).
