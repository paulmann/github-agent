# Импорт пакета в другой агент

Пакет не требует установки в систему: он лежит каталогом и вызывается по пути. «Импорт»
означает две вещи — копию пакета в каталоге навыков агента и строку правил, которая
говорит агенту, где эта копия лежит и чем проверить, что она цела.

## Что именно копируется

Команда `install` копирует `AGENTS.md`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
`SECURITY.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, `CITATION.cff`, каталоги
`skills/`, `tools/`, `tests/`, `reference/`, `docs/`, `wiki/`, `.github/` и пишет рядом
манифест `.install.json` с sha256 каждого файла. Тесты копируются вместе с кодом — иначе
в установленной копии нельзя ни прогнать `selftest`, ни доказать, что она работает так,
как проверяли.

## AutoClaw2

Каталог навыков: `%USERPROFILE%\.pi\agent\skills`. Правила агента читаются из
`%USERPROFILE%\.pi\agent\AGENTS.md`.

```powershell
git clone https://github.com/paulmann/github-agent.git "$env:USERPROFILE\src\github-agent"
Set-Location "$env:USERPROFILE\src\github-agent"

python tools\ghagent.py install --profile autoclaw --write
python tools\ghagent.py verify-install --profile autoclaw
python tools\ghagent.py snippet --profile autoclaw
```

Вывод `snippet` добавляется в `%USERPROFILE%\.pi\agent\AGENTS.md`. После перезапуска
сессии агент видит навык; в текущей сессии список навыков уже прочитан, поэтому новый
навык появляется со следующей.

## HARNESS

Каталог навыков: `%USERPROFILE%\.dsh\skills`, правила — `%USERPROFILE%\.dsh\AGENTS.md`.

```powershell
python tools\ghagent.py install --profile harness --write
python tools\ghagent.py verify-install --profile harness
python tools\ghagent.py snippet --profile harness
```

Дальше то же: блок из `snippet` вставляется в `.dsh\AGENTS.md`.

## SagaAI

У SagaAI нет измеренного каталога навыков, поэтому путь задаётся явно. Если агент читает
правила из `AGENTS.md` проекта, достаточно указать в этом файле путь к пакету и команду
проверки — этого хватает, потому что пакет самодостаточен.

```bash
git clone https://github.com/paulmann/github-agent.git <каталог>
python tools/ghagent.py install --target <каталог навыков SagaAI> --write
python tools/ghagent.py snippet --target <каталог навыков SagaAI>
```

Блок `snippet` печатает текст, а не пишет файл: решение, куда его вставить, остаётся за
владельцем агента.

## Проверка импорта

```bash
python tools/ghagent.py verify-install --profile <autoclaw|harness>   # код 0 — копия цела
python tools/ghagent.py --version                                     # печатает версию
```

`verify-install` сравнивает sha256 с манифестом. Возможные исходы:

| Исход | Значение | Действие |
|---|---|---|
| `verify.ok`, код `0` | копия совпадает с установленной | работать |
| `verify.changed`, код `1` | файл изменён после установки | переустановить пакет |
| `verify.missing`, код `1` | файл удалён | переустановить пакет |
| `verify.manifest`, код `1` | каталог установлен не пакетом | не доверять, поставить заново |
| `verify.extra`, `info` | в каталоге есть файл вне манифеста | проверить, не мусор ли |

## Обновление

```bash
git -C <каталог пакета> pull
python tools/ghagent.py install --profile <профиль> --write
python tools/ghagent.py verify-install --profile <профиль>
```

`install` перезаписывает файлы и заново пишет манифест, поэтому после обновления `verify`
снова зелёный. Старая копия не архивируется: пакет восстанавливается из git в один шаг.

## Удаление

```bash
python tools/ghagent.py uninstall --profile <профиль> --write
```

Удаление без манифеста `.install.json` отклоняется: команда не имеет права сносить
каталог, который ставил кто-то другой. Вставленный ранее блок правил удаляется из
`AGENTS.md` вручную — пакет не редактирует чужие файлы правил.
