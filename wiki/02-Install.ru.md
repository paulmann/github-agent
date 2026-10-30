# Установка

Требуется Python 3.11 или новее (проверено на 3.13; CI гоняет 3.11 и 3.13). Зависимостей при
запуске нет, Pillow необязателен: он добавляет только выпуск PNG в `assets render`.

Есть три семейства установки, и они не равнозначны. Пакетные менеджеры ставят только CLI
`ghagent`. Git-клон несёт весь пакет — `tools/`, `tests/`, `skills/`, `reference/`, `wiki/` и
`docs/` — и только из него работают команды `install`, `verify-install`, `snippet` и
`uninstall`. Docker и GitHub Action не требуют ни Python, ни клона на хосте.

## Из PyPI: uv, pipx или pip

```bash
uv tool install github-agent-cli        # изолированное окружение инструмента
pipx install github-agent-cli           # изолированное виртуальное окружение
pip install github-agent-cli            # в текущее окружение
ghagent --version                   # github-agent 1.2.1
```

Консольная команда — `ghagent`, дистрибутив — `github-agent`. Колесо содержит только CLI,
поэтому при установке из колеса `selftest` и `install` завершаются кодом `2` с указанием на
git-клон. Так и задумано: тесты и шаблоны навыков в колесо не входят.

## Необязательная поддержка PNG

`assets render` всегда пишет SVG. Для PNG нужен Pillow:

```bash
pip install "github-agent-cli[png]"
uv tool install --with pillow github-agent-cli
```

Без Pillow команда выпускает SVG и говорит, почему PNG нет.

## Из репозитория

Клон — это установка для разработки и источник операций с пакетом:

```bash
git clone https://github.com/paulmann/github-agent.git
cd github-agent

python tools/ghagent.py --version
python tools/ghagent.py selftest
pip install -e .                    # необязательно: команда `ghagent` из этого дерева
```

`selftest` запускает тесты пакета и печатает `PASS` при коде `0`. Если тесты падают — работать
этой копией нельзя, нужно взять чистую.

## Docker

Образ собирается из клона, поэтому релиз на PyPI ему не нужен:

```bash
docker build -t ghagent .
cd /path/to/your/repository
docker run --rm -v "$PWD:/repo" ghagent audit .
```

Рабочий каталог образа — `/repo`, точка входа — `ghagent`. Образ в реестр в рамках 1.2.1 не
публикуется; тег — локальная договорённость. В образе только CLI, поэтому `selftest` и
`install` там тоже завершаются кодом `2`. Подробности: [пример Docker](https://github.com/paulmann/github-agent/blob/main/examples/docker.md).

## GitHub Action

Составное действие ставит пакет из своего же checkout, поэтому работает сразу после появления
тега:

```yaml
- uses: actions/checkout@v7
- uses: paulmann/github-agent@v1.2.1
  with:
    command: audit .
    min-score: "80"
```

Входы: `command` (по умолчанию `audit . --min-score 80`), `min-score`, `working-directory`,
`python-version`, `github-token`. Полный workflow: [использование в CI](https://github.com/paulmann/github-agent/blob/main/examples/ci-usage.md).

## Первый аудит

```bash
cd <ваш репозиторий>
ghagent audit .
```

Внутри клона та же команда выглядит как `python tools/ghagent.py audit .`. Команда печатает
оценку гигиены, список пунктов со статусом и находки с `файл:строка` и идентификатором правила.

| Код возврата | Значение |
|---|---|
| `0` | блокирующих находок нет |
| `1` | есть находки уровня `error` |
| `2` | ошибка вызова или окружения: неверный путь, нет файла, нет токена |

## Установка навыка агенту

Этот шаг требует клона: копируется пакет, а не CLI.

```bash
python tools/ghagent.py install --profile autoclaw --write   # AutoClaw2
python tools/ghagent.py install --profile harness  --write   # HARNESS
python tools/ghagent.py install --target <каталог> --write   # SagaAI
```

Команда копирует пакет в каталог навыков, пишет манифест `.install.json` с sha256 каждого
файла и печатает блок правил для `AGENTS.md`. Подробности — [Импорт в другой агент](07-Import.ru).

## Проверка установки

```bash
ghagent --version                            # колесо или editable-установка
python tools/ghagent.py selftest             # только клон
python tools/ghagent.py verify-install --profile autoclaw
```

`verify-install` отвечает на один вопрос: та ли это копия, что прошла тесты. `verify.ok` и код
`0` означают «да»; любое расхождение печатается с именем файла. Расхождение версии
`ghagent --version` с релизом, который ставили, означает неверное окружение в `PATH`, а не
сломанный пакет.

## Требования к окружению

| Что | Требование |
|---|---|
| Python | 3.11+ |
| `git` | нужен для `changelog suggest` и `wiki publish` |
| `gh` CLI или `GITHUB_TOKEN` | нужен только для `audit --repo`, `meta`, `wiki publish` |
| Сеть | только для команд, работающих с GitHub |
| Pillow | необязателен, включает PNG в `assets render` |
| pre-commit | необязателен, запускает хуки из релизного тега |

Остальные команды работают без сети: `doc`, `audit .`, `changelog check`,
`changelog release`, `wiki build`, `wiki verify`, `assets check`.

## Дальше

- [Контракты файлов](03-Repository-Contract.ru) — что проверяется.
- [Работа с вики](04-Wiki-Workflow.ru) — сборка и публикация.
- [Упаковка и выпуск](https://github.com/paulmann/github-agent/blob/main/docs/PACKAGING.md) —
  колесо, sdist, Action, Docker и порядок публикации.
