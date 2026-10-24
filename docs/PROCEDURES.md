# Процедуры

Пять работ, которые повторяются в каждом репозитории. Для каждой: когда выполняется, какие
команды, что считается успехом и что делать при провале.

## 1. Аудит репозитория

**Когда:** проект опубликован, README писался давно, метаданные заполнялись «на глаз».

```bash
python tools/ghagent.py audit . --json > audit.json
python tools/ghagent.py audit --repo owner/name
python tools/ghagent.py report . --out AUDIT.md
```

**Успех:** оценка не ниже 80%, блокирующих находок нет, число осмотренных пунктов больше
двадцати. Оценка ниже порога — не приговор, а порядок работы: сначала `error`, потом
`warn`, `info` не трогаем.

**Провал:** `remote.unavailable` — нет `gh` и нет `GITHUB_TOKEN`. Это не «всё хорошо»:
метаданные не осмотрены, и отчёт об этом говорит.

## 2. README и AGENTS.md

**Когда:** новый проект, либо README перестал отвечать на вопрос «как запустить».

1. Взять каркасы: `reference/readme-template.md`, `reference/agents-template.md`.
2. Заполнить фактами: команды, пути, версии, числа с источником.
3. Проверить: `python tools/ghagent.py doc --root .`.

**Успех:** `md.h1` — один заголовок, `readme.summary` — абзац описания,
`readme.badges` — не меньше трёх бейджей, `readme.install`/`readme.usage`/`readme.license`
на месте, ссылки живые.

**Провал:** `md.toc` — оглавление разошлось с заголовками. Правится не руками, а
пересборкой списка: якорь = заголовок в нижнем регистре, знаки препинания удалены,
пробелы заменены дефисами.

## 3. Выпуск версии

**Когда:** накопились изменения в `[Unreleased]`.

```bash
python tools/ghagent.py changelog check
python tools/ghagent.py changelog suggest --since v1.1.0
python tools/ghagent.py changelog release 1.2.0 --write
python tools/ghagent.py changelog notes 1.2.0 > release-body.md
gh release create v1.2.0 --notes-file release-body.md --title v1.2.0
```

**Успех:** новая версия с ISO-датой, `[Unreleased]` снова пустой, ссылки сравнения
обновлены, `changelog check` без ошибок, текст релиза прочитан человеком.

**Провал:** `changelog.duplicate` — версия уже есть; `changelog.empty-version` — в
`[Unreleased]` нет записей. Выпускать пустую версию нельзя: журнал перестаёт что-либо
значить.

## 4. Вики

**Когда:** документация переросла README, либо вики существует, но навигации в ней нет.

```bash
python tools/ghagent.py wiki init --repo owner/name --title "Имя проекта"   # если вики нет
python tools/ghagent.py wiki build
python tools/ghagent.py wiki verify
python tools/ghagent.py wiki publish --repo owner/name                     # сухой прогон
python tools/ghagent.py wiki publish --repo owner/name --push              # публикация
```

**Успех:** `wiki build` без ошибок, `wiki verify` без ошибок, сухой прогон показывает
только ожидаемые файлы, список `kept` просмотрен, после `--push` страница открывается.

**Провал:** `wiki.page-unlisted` — файл есть, в манифесте его нет. Такая страница
невидима, поэтому это ошибка, а не замечание. `wiki.image-relative` — картинка лежит
внутри вики-исходников; её нужно перенести в дерево репозитория и подключить абсолютным
URL.

## 5. Метаданные и публикация

**Когда:** репозиторий публикуется, либо описание и темы перестали соответствовать
содержимому.

```bash
python tools/ghagent.py meta suggest
python tools/ghagent.py meta apply --repo owner/name --description "…" --topics a,b
python tools/ghagent.py meta apply --repo owner/name --description "…" --topics a,b --write
python tools/ghagent.py audit --repo owner/name --http
```

**Успех:** описание до 200 символов и начинается с категории, тем 8–20, все в нижнем
регистре через дефис, домашняя страница отвечает `200`, чтение после записи совпало с
запрошенным.

**Провал:** `meta.topics-overflow` — больше двадцати тем, API сохранит только двадцать.
`meta.verify` — запись не применилась; читать ответ, а не верить вызову.

## Порядок, если всё сломалось

1. `python tests/run_tests.py` — работает ли сам пакет.
2. `python tools/ghagent.py verify-install --profile <профиль>` — та ли копия.
3. `python tools/ghagent.py doc --root . --json` — что именно нарушено, с файлом и строкой.
4. Только после этого — правка файлов. Правка «по ощущению» возвращает те же дефекты.
