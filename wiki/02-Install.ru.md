# Установка

Требуется Python 3.11 или новее (проверено на 3.13.15). Ни `pip install`, ни сборки, ни
системных пакетов.

## Из репозитория

```bash
git clone https://github.com/paulmann/github-agent.git
cd github-agent

python tools/ghagent.py --version
python tools/ghagent.py selftest
```

`selftest` запускает тесты пакета и печатает `selftest: PASS` при коде `0`. Если тесты
падают — работать этой копией нельзя, нужно взять чистую.

## Первый аудит

```bash
cd <ваш репозиторий>
python <путь>/github-agent/tools/ghagent.py audit .
```

Команда печатает оценку гигиены, список пунктов со статусом и находки с `файл:строка`.

| Код возврата | Значение |
|---|---|
| `0` | блокирующих находок нет |
| `1` | есть находки уровня `error` |
| `2` | ошибка вызова: неверный путь, нет файла |

## Установка навыка агенту

```bash
python tools/ghagent.py install --profile autoclaw --write   # AutoClaw2
python tools/ghagent.py install --profile harness  --write   # HARNESS
python tools/ghagent.py install --target <каталог> --write   # SagaAI
```

Команда копирует пакет в каталог навыков, пишет манифест `.install.json` с sha256 каждого
файла и печатает блок правил для `AGENTS.md`. Подробности — [Импорт в другой агент](07-Import.ru).

## Проверка установки

```bash
python tools/ghagent.py verify-install --profile autoclaw
```

`verify.ok` и код `0` означают, что установленная копия совпадает с проверенной. Любое
расхождение печатается с именем файла.

## Требования к окружению

| Что | Требование |
|---|---|
| Python | 3.11+ |
| `git` | нужен для `changelog suggest` и `wiki publish` |
| `gh` CLI или `GITHUB_TOKEN` | нужен только для `audit --repo`, `meta`, `wiki publish` |
| Сеть | только для команд, работающих с GitHub |

Остальные команды работают без сети: `doc`, `audit .`, `changelog check`,
`changelog release`, `wiki build`, `wiki verify`.

## Дальше

- [Контракты файлов](03-Repository-Contract.ru) — что проверяется.
- [Работа с вики](04-Wiki-Workflow.ru) — сборка и публикация.
