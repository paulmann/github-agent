# Контракты файлов

Проверка возможна только там, где есть контракт. Ниже — что именно пакет считает
правильным и как это проверяется.

## README.md

| Пункт | Правило | Правило проверки |
|---|---|---|
| Заголовок | один `H1`, до 60 символов | `readme.h1` |
| Описание | абзац сразу после заголовка: что это и для кого | `readme.summary` |
| Бейджи | 3–8 штук: CI, релиз, лицензия, среда | `readme.badges` |
| Оглавление | обязательно, если документ длиннее 200 строк | `readme.toc` |
| Установка | раздел `Installation` или `Установка` | `readme.install` |
| Использование | раздел `Usage` или `Быстрый старт` | `readme.usage` |
| Лицензия | раздел `License` или `Лицензия` | `readme.license` |
| Код | каждый блок с языком | `readme.code-fence` |

## AGENTS.md

| Пункт | Зачем |
|---|---|
| Копируемые команды | агент не должен догадываться о синтаксисе |
| Раздел проверки | чем убедиться, что работа сделана |
| Раздел запретов | что нельзя и почему |
| Карта, а не энциклопедия | `agents.md-length` предупреждает после 120 строк; подробности — в `docs/` |
| Ссылка на таблицу ловушек | признак, по которому ловушка узнаётся, остаётся в подробном документе |

С версии 1.2.0 корневой `AGENTS.md` — карта до 120 строк: каталог правил, контракты файлов и
таблица из 15 ловушек живут в
[docs/RULES.md](https://github.com/paulmann/github-agent/blob/main/docs/RULES.md), работа с
вики — в [docs/WIKI.md](https://github.com/paulmann/github-agent/blob/main/docs/WIKI.md), модули
и коды выхода — в
[docs/ARCHITECTURE.md](https://github.com/paulmann/github-agent/blob/main/docs/ARCHITECTURE.md).

## CHANGELOG.md

```markdown
# Changelog

All notable changes are documented here. Format: Keep a Changelog 2.0.0, SemVer 2.0.0.

## [Unreleased]

## [1.1.0] - 2026-10-20

### Added

- Something a user can see.

[Unreleased]: https://github.com/owner/repo/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/owner/repo/compare/v1.0.0...v1.1.0
```

Шесть типов: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. Дата —
ISO. Новые версии выше старых. `Unreleased` сверху.

## wiki/wiki.json

Манифест задаёт порядок и навигацию. Файл, которого нет в манифесте, — ошибка: страница
существует, но не находится.

```json
{
  "repo": "owner/name",
  "branch": "main",
  "title": "Имя проекта",
  "footer": "MIT",
  "groups": [
    {"title": "Начало", "pages": ["Home.md", "01-Install.md"]}
  ]
}
```

## Что делает `doc`

```bash
python tools/ghagent.py doc --root .
```

| Группа | Правила |
|---|---|
| Текст | `doc.bom`, `doc.crlf`, `doc.final-newline`, `doc.tab-indent` |
| Структура | `md.h1`, `md.heading-skip`, `md.fence` |
| Таблицы | `md.table` |
| Ссылки | `md.link-local`, `md.link-anchor`, `md.link-dir` |
| Оглавление | `md.toc` |
| Разметка | `md.alert`, `md.image-alt`, `md.hard-break` |
| Приватность | `privacy.secret`, `privacy.abs-path`, `privacy.email` |

Файл с маркером `<!-- ghagent: template -->` освобождается от проверки ссылок: шаблон
содержит неразрешённые плейсхолдеры намеренно.

## Правило, которое важнее остальных

Если правило осмотрело ноль объектов, оно **не** считается пройденным. В отчёте такая
строка называется `coverage.skipped`, а пустое дерево даёт ошибку `doc.no-text-files`.
Проверка, которая ничего не проверила, опаснее отсутствия проверки: она создаёт
уверенность.

## Дальше

- [Работа с вики](04-Wiki-Workflow.ru).
- [Ловушки платформы](06-Traps.ru).
