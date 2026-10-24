# Импорт в другой агент

Пакет импортируется двумя действиями: копия в каталоге навыков агента и строка правил,
которая говорит, где эта копия и чем проверить её целостность.

## Каталоги

| Агент | Каталог навыков | Файл правил |
|---|---|---|
| AutoClaw2 | `%USERPROFILE%\.pi\agent\skills` | `%USERPROFILE%\.pi\agent\AGENTS.md` |
| HARNESS | `%USERPROFILE%\.dsh\skills` | `%USERPROFILE%\.dsh\AGENTS.md` |
| SagaAI | задаётся вручную | `AGENTS.md` проекта |

## Установка

```bash
python tools/ghagent.py install --profile autoclaw --write
python tools/ghagent.py install --profile harness  --write
python tools/ghagent.py install --target <каталог>  --write
```

Команда копирует пакет (включая `tests/`, чтобы `selftest` работал на месте), пишет
манифест `.install.json` с sha256 каждого файла и печатает блок правил.

## Блок правил

Его печатает команда `snippet`:

```bash
python tools/ghagent.py snippet --profile harness
```

Содержимое блока: путь к пакету, требование прочитать файл правил пакета, команда проверки
установки и правило «одна задача — одна команда». Файлы правил агента команда не правит:
это решение владельца.

## Проверка

```bash
python tools/ghagent.py verify-install --profile harness
python tools/ghagent.py selftest
```

| Исход | Код | Значение |
|---|---|---|
| `verify.ok` | 0 | копия совпадает с установленной |
| `verify.changed` | 1 | файл изменён после установки |
| `verify.missing` | 1 | файл удалён |
| `verify.manifest` | 1 | каталог ставил не пакет |

## Обновление и удаление

```bash
git -C <каталог пакета> pull
python tools/ghagent.py install --profile <профиль> --write
python tools/ghagent.py verify-install --profile <профиль>

python tools/ghagent.py uninstall --profile <профиль> --write
```

`uninstall` отказывается удалять каталог без манифеста: он не имеет права сносить то, что
ставил кто-то другой.

## Ловушки

| Ловушка | Признак | Что делать |
|---|---|---|
| Навык не виден агенту | каталог есть, агент его не знает | список навыков читается при старте сессии — перезапустить сессию |
| Копию правили руками | `verify.changed` | переустановить |
| Установка в чужой каталог | `uninstall` отказывается | указать `--target` явно |
| Тестов нет в поставке | `selftest` не находит раннер | копировать `tests/` вместе с `tools/` |

## Дальше

- [Установка](02-Install).
- [Работа с вики](04-Wiki-Workflow).
