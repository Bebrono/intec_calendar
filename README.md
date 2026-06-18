# Calendar Sync Service

Прототип Python-сервиса для синхронизации событий между календарями разных экосистем.

Проект показывает основную бизнес-логику синхронизации:

- событие, созданное в одном календаре, появляется у остальных участников;
- изменение события распространяется на его копии;
- удаление или статус `deleted` распространяется на копии;
- дубликаты не создаются при повторных запусках;
- циклическая синхронизация предотвращается через `sync_group_id` и служебные метки;
- соответствия между событиями сохраняются в SQLite;
- действия сервиса пишутся в консоль, файл лога и таблицу логов.

Основной режим работает без внешних аккаунтов через JSON-файлы. Дополнительно уже подключены реальные адаптеры Google Calendar и Yandex Calendar.

## Быстрый ответ: что тут готово

Готово:

- JSON mock-адаптеры для 4 календарей;
- общая модель события `CalendarEvent`;
- SQLite-хранилище соответствий событий;
- защита от дублей и циклов синхронизации;
- демонстрационный сценарий `python main.py demo`;
- реальный Google Calendar adapter для участника `developer_2`;
- реальный Yandex Calendar adapter через CalDAV для участника `developer_1`;
- smoke-тесты и integration-demo для Google и Yandex;
- автотесты.

Пока не готово:

- реальный Outlook Calendar adapter;
- полноценный веб-интерфейс;
- production-настройка OAuth/секретов.

## Как скачать проект

Репозиторий:

[https://github.com/Bebrono/intec_calendar](https://github.com/Bebrono/intec_calendar)

Через Git:

```powershell
git clone https://github.com/Bebrono/intec_calendar.git
cd intec_calendar
git checkout yandex-live-sync
```

Ветка `yandex-live-sync` содержит актуальную версию с JSON, Google и Yandex. Если эта ветка уже смержена в `main`, команду `git checkout yandex-live-sync` можно пропустить.

Можно скачать ZIP с GitHub:

1. Открыть репозиторий.
2. Нажать `Code`.
3. Нажать `Download ZIP`.
4. Распаковать архив.
5. Открыть терминал в распакованной папке.

## Что нужно установить

Минимально:

- Python 3.11 или новее;
- Git, если проект скачивается через `git clone`;
- интернет, если проверяются реальные Google/Yandex календари.

Проверить Python:

```powershell
python --version
```

Если Windows пишет, что `python` не найден, попробуйте:

```powershell
py -3.11 --version
```

Если не работает и это, установите Python с [python.org](https://www.python.org/downloads/) и включите галочку `Add Python to PATH`.

## Установка зависимостей

Откройте терминал в папке проекта.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если PowerShell не дает активировать окружение, выполните в этом же окне:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

После установки можно проверить, что проект хотя бы импортируется и тесты запускаются:

```powershell
pytest
```

Ожидаемый результат: тесты завершаются со статусом `passed`.

## Участники календарей

В прототипе есть 4 участника:

| Участник | Система | Режим по умолчанию |
| --- | --- | --- |
| `developer_1` | Yandex Calendar | JSON-файл `yandex_developer_1.json` |
| `developer_2` | Google Calendar | JSON-файл `google_developer_2.json` |
| `manager` | Outlook Calendar | JSON-файл `outlook_manager.json` |
| `leader` | Yandex Calendar | JSON-файл `yandex_leader.json` |

При запуске с флагом `--real-google` участник `developer_2` работает через настоящий Google Calendar.

При запуске с флагом `--real-yandex` участник `developer_1` работает через настоящий Yandex Calendar.

Остальные участники в этих режимах продолжают работать через JSON-файлы. Это сделано специально: можно постепенно заменять mock-адаптеры реальными API, не переписывая `SyncService`.

## Структура проекта

```text
calendar-sync-service/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── adapters/
│   │   ├── base.py
│   │   ├── file_calendar_adapter.py
│   │   ├── google_calendar_adapter.py
│   │   └── yandex_calendar_adapter.py
│   ├── models/
│   │   └── event.py
│   ├── services/
│   │   ├── sync_service.py
│   │   ├── event_mapper.py
│   │   ├── google_*.py
│   │   └── yandex_*.py
│   ├── storage/
│   │   ├── database.py
│   │   └── repositories.py
│   └── logger.py
├── data/
│   ├── input/
│   └── output/
├── logs/
└── tests/
```

Важные файлы:

- `main.py` - консольная точка входа;
- `app/services/sync_service.py` - главная логика синхронизации;
- `app/adapters/base.py` - общий интерфейс календаря;
- `app/adapters/file_calendar_adapter.py` - JSON-адаптер;
- `app/adapters/google_calendar_adapter.py` - Google Calendar API adapter;
- `app/adapters/yandex_calendar_adapter.py` - Yandex CalDAV adapter;
- `data/output/*.json` - рабочие JSON-календари;
- `data/sync.db` - локальная SQLite-база;
- `logs/sync.log` - файл логов.

## Как работает синхронизация

1. Сервис читает события из всех подключенных календарей.
2. Каждое событие приводится к общей модели `CalendarEvent`.
3. Сервис проверяет SQLite-таблицу `event_mappings`.
4. Если событие новое, создается `sync_group_id`.
5. Копии события создаются в остальных календарях.
6. В описание копий добавляются технические метки:

```text
[SYNC_ID: sync_xxx]
[SOURCE: outlook]
```

7. При повторном запуске сервис видит метки и записи в БД, поэтому не создает дубликаты.
8. Если у одной копии `updated_at` новее, сервис обновляет остальные копии.
9. Если событие получает `status: deleted`, остальные копии тоже помечаются удаленными.
10. Итог работы пишется в консоль, `logs/sync.log` и SQLite.

## Самая простая проверка без внешних аккаунтов

Эта проверка не требует Google, Yandex, OAuth, паролей и интернета.

Запустите:

```powershell
python main.py demo
```

Что делает demo:

1. Очищает рабочие JSON-календари в `data/output`.
2. Очищает `data/sync.db`.
3. Очищает `logs/sync.log`.
4. Создает событие в календаре менеджера `outlook_manager.json`.
5. Запускает синхронизацию.
6. Показывает, что копии появились у остальных участников.
7. Меняет название и время события.
8. Запускает синхронизацию второй раз.
9. Показывает, что изменения дошли до копий.
10. Помечает событие как `deleted`.
11. Запускает синхронизацию третий раз.
12. Показывает, что копии тоже стали `deleted`.

Как понять, что demo работает:

- в консоли появляются шаги `Demo step 1`, `Demo step 2`, `Demo step 3`;
- после первого шага видно, что событие есть у `outlook/manager`, `google/developer_2`, `yandex/developer_1`, `yandex/leader`;
- после второго шага у всех копий новое название;
- после третьего шага у всех копий статус `deleted`;
- в `logs/sync.log` появляются записи о создании, обновлении и удалении;
- в `data/sync.db` создаются записи соответствий.

## Обычная JSON-синхронизация

Команда:

```powershell
python main.py sync
```

Этот режим использует только файлы из `data/output`:

- `data/output/outlook_manager.json`;
- `data/output/google_developer_2.json`;
- `data/output/yandex_developer_1.json`;
- `data/output/yandex_leader.json`.

Как проверить:

1. Откройте `data/output/outlook_manager.json`.
2. Добавьте или измените событие.
3. Убедитесь, что `updated_at` стал новее, чем был.
4. Запустите `python main.py sync`.
5. Откройте остальные JSON-файлы.
6. Проверьте, что событие появилось или обновилось.

Пример успешного вывода:

```text
Synchronization complete: groups=1, created=3, updated=0, deleted=0
```

Если запустить команду повторно без изменений, новые дубликаты появляться не должны.

## Проверка логов

Windows PowerShell:

```powershell
Get-Content logs\sync.log -Tail 50
```

Linux/macOS:

```bash
tail -n 50 logs/sync.log
```

В логах должны быть записи о старте синхронизации, найденных событиях, созданных копиях, обновлениях и удалениях.

## Проверка SQLite-базы

В базе `data/sync.db` есть таблица `event_mappings`. Она хранит связь между копиями одного события.

Быстро посмотреть записи можно так:

```powershell
python -c "import sqlite3; con=sqlite3.connect('data/sync.db'); print(con.execute('select sync_group_id, calendar_owner, calendar_system, external_event_id, is_original from event_mappings').fetchall())"
```

Ожидаемая логика:

- у одного события один общий `sync_group_id`;
- для каждого участника есть отдельная строка;
- у оригинального события `is_original` равен `1`;
- у копий `is_original` равен `0`.

## Google Calendar: подготовка

Google-адаптер нужен, чтобы проверить не только JSON, но и реальный Google Calendar API.

В учебном прототипе в репозитории лежит OAuth desktop client файл вида:

```text
client_secret_*.json
```

Для реального production-проекта такой файл лучше не хранить в публичном репозитории. Здесь он оставлен для упрощения проверки прототипа.

Перед проверкой Google:

1. В Google Cloud должен быть включен Google Calendar API.
2. Аккаунт проверяющего должен быть добавлен в test users OAuth-приложения, если приложение находится в testing-режиме.
3. В проекте должен быть файл `client_secret_*.json`.

## Google Calendar: авторизация

Сначала получите ссылку авторизации:

```powershell
python main.py google auth-url
```

Команда выведет длинную ссылку. Откройте ее в браузере, выберите Google-аккаунт и разрешите доступ.

После разрешения Google перекинет на адрес вида:

```text
http://localhost/?state=...&code=...&scope=...
```

Скопируйте весь этот URL и передайте его команде:

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
```

Если все хорошо, появится сообщение:

```text
Google token saved to ...
```

Токен сохраняется локально в `data/google_token.json`. Этот файл добавлен в `.gitignore` и не должен попадать в репозиторий.

## Google Calendar: smoke-test

Smoke-test проверяет прямой CRUD через Google API:

```powershell
python main.py google smoke-test
```

Что делает команда:

1. Создает временное событие в Google Calendar.
2. Обновляет его название.
3. Удаляет событие.
4. Печатает результат в консоль.

Успешный результат выглядит примерно так:

```text
Google Calendar smoke-test complete:
- created event id: ...
- created title: ...
- updated title: ...
- deleted status: cancelled
```

Это значит, что API-доступ работает: сервис умеет создавать, обновлять и удалять события в Google Calendar.

## Google Calendar: отдельный календарь для синхронизации

Чтобы не мусорить в основном календаре, сервис создает отдельный календарь для тестов.

Создать или переиспользовать его:

```powershell
python main.py google create-sync-calendar
```

Ожидаемый результат:

```text
Created Google sync calendar:
- summary: Calendar Sync Service Test
- calendar_id: ...
```

Или:

```text
Using existing Google sync calendar:
- summary: Calendar Sync Service Test
- calendar_id: ...
```

ID календаря сохраняется в `data/google_calendar_config.json`. Этот файл локальный и не коммитится.

Очистить события из тестового Google-календаря:

```powershell
python main.py google clear-sync-calendar
```

## Google Calendar: integration-demo

Команда:

```powershell
python main.py google integration-demo
```

Что проверяется:

- событие из JSON-календаря попадает в настоящий Google Calendar;
- событие из настоящего Google Calendar попадает в JSON-календари;
- обновления не создают дубликаты;
- служебные метки и SQLite-соответствия работают с реальным API.

Как понять, что все правильно:

- в консоли нет traceback/ошибок;
- в Google Calendar появляется тестовый календарь `Calendar Sync Service Test`;
- в нем появляются тестовые события;
- в `data/output/*.json` появляются копии событий;
- повторный запуск не плодит одинаковые события.

## Google Calendar в общей синхронизации

Команда:

```powershell
python main.py sync --real-google
```

В этом режиме:

- `developer_2` работает через реальный Google Calendar;
- `developer_1`, `manager`, `leader` работают через JSON-файлы;
- вся бизнес-логика остается той же самой.

Можно включить Google и Yandex одновременно:

```powershell
python main.py sync --real-google --real-yandex
```

## Yandex Calendar: подготовка

Yandex-адаптер работает через CalDAV.

Для входа нужен не обычный пароль от почты, а пароль приложения Yandex.

Создайте локальный файл `.env` из примера:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Откройте `.env` и заполните:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru
YANDEX_USERNAME=Bebrono@yandex.ru
YANDEX_APP_PASSWORD=your_yandex_app_password
```

Файл `.env` добавлен в `.gitignore`. Не коммитьте его и не отправляйте пароль в репозиторий.

## Yandex Calendar: проверка авторизации

Команда:

```powershell
python main.py yandex check-auth
```

Успешный результат:

```text
Yandex CalDAV auth OK, calendars found: ...
```

Если вместо этого ошибка авторизации, чаще всего причина одна из этих:

- указан обычный пароль от аккаунта, а не пароль приложения;
- в `.env` ошибка в почте;
- пароль скопирован с пробелом;
- CalDAV URL указан неправильно.

## Yandex Calendar: отдельный календарь для синхронизации

Создать или переиспользовать тестовый календарь:

```powershell
python main.py yandex create-sync-calendar
```

Ожидаемый результат:

```text
Created Yandex sync calendar:
- name: Calendar Sync Service Yandex Test
- calendar_url: ...
```

Или:

```text
Using existing Yandex sync calendar:
- name: Calendar Sync Service Yandex Test
- calendar_url: ...
```

URL календаря сохраняется в `data/yandex_calendar_config.json`. Этот файл локальный и не коммитится.

Очистить события из тестового Yandex-календаря:

```powershell
python main.py yandex clear-sync-calendar
```

## Yandex Calendar: smoke-test

Команда:

```powershell
python main.py yandex smoke-test
```

Что делает команда:

1. Создает временное событие в Yandex Calendar.
2. Обновляет его название.
3. Помечает событие удаленным.
4. Печатает результат.

Успешный результат выглядит примерно так:

```text
Yandex Calendar smoke-test complete:
- created event id: ...
- created title: ...
- updated title: ...
- deleted status: deleted
```

Это значит, что CalDAV-доступ работает и адаптер умеет выполнять основные операции.

## Yandex Calendar: integration-demo

Команда:

```powershell
python main.py yandex integration-demo
```

Что проверяется:

- событие из JSON-календаря попадает в настоящий Yandex Calendar;
- событие из настоящего Yandex Calendar попадает в JSON-календари;
- обновления не создают дубликаты;
- служебные метки и SQLite-соответствия работают с CalDAV.

Как понять, что все правильно:

- в консоли нет traceback/ошибок;
- в Yandex Calendar есть календарь `Calendar Sync Service Yandex Test`;
- в нем появляются тестовые события;
- в `data/output/*.json` появляются копии событий;
- повторный запуск не создает дубликаты.

## Yandex Calendar в общей синхронизации

Команда:

```powershell
python main.py sync --real-yandex
```

В этом режиме:

- `developer_1` работает через реальный Yandex Calendar;
- `developer_2`, `manager`, `leader` работают через JSON-файлы;
- логика синхронизации остается общей.

## Полная проверка проекта для проверяющего

Если нужно быстро убедиться, что проект работает корректно, достаточно пройти такой маршрут:

1. Скачать проект.
2. Перейти в ветку `yandex-live-sync`.
3. Создать виртуальное окружение.
4. Установить зависимости.
5. Запустить тесты:

```powershell
pytest
```

6. Запустить JSON-demo:

```powershell
python main.py demo
```

7. Проверить, что в консоли были 3 шага: создание, обновление, удаление.
8. Открыть `data/output/*.json` и убедиться, что событие есть у всех участников.
9. Открыть `logs/sync.log` и убедиться, что действия записались.
10. При наличии Google-доступа выполнить:

```powershell
python main.py google auth-url
python main.py google auth-finish "FINAL_LOCALHOST_URL"
python main.py google create-sync-calendar
python main.py google smoke-test
python main.py google integration-demo
```

11. При наличии Yandex app password выполнить:

```powershell
python main.py yandex check-auth
python main.py yandex create-sync-calendar
python main.py yandex smoke-test
python main.py yandex integration-demo
```

Если все эти шаги проходят без ошибок, значит прототип работает правильно.

## Как понять, что дубликаты не создаются

1. Запустите:

```powershell
python main.py demo
```

2. Потом запустите:

```powershell
python main.py sync
```

3. Откройте JSON-файлы в `data/output`.
4. Убедитесь, что одно и то же событие не появилось второй, третий или четвертый раз.

Дубликаты предотвращаются двумя способами:

- через таблицу `event_mappings` в SQLite;
- через метку `[SYNC_ID: ...]` в описании события.

## Как понять, что обновления работают

В JSON-событии измените:

- `title`;
- или `start_time`;
- или `end_time`;
- и обязательно сделайте `updated_at` новее.

Пример:

```json
{
  "title": "Командная встреча: новое время",
  "updated_at": "2026-06-15T18:00:00"
}
```

После запуска:

```powershell
python main.py sync
```

такие же изменения должны появиться у копий в остальных календарях.

## Как понять, что удаление работает

В оригинальном событии поставьте:

```json
"status": "deleted"
```

и обновите:

```json
"updated_at": "2026-06-15T19:00:00"
```

После запуска:

```powershell
python main.py sync
```

копии события в остальных календарях тоже должны получить статус `deleted` или быть удалены адаптером.

## Команды CLI

Основные:

```powershell
python main.py demo
python main.py sync
python main.py sync --real-google
python main.py sync --real-yandex
python main.py sync --real-google --real-yandex
```

Google:

```powershell
python main.py google auth-url
python main.py google auth-finish "FINAL_LOCALHOST_URL_OR_CODE"
python main.py google smoke-test
python main.py google create-sync-calendar
python main.py google clear-sync-calendar
python main.py google integration-demo
```

Yandex:

```powershell
python main.py yandex check-auth
python main.py yandex create-sync-calendar
python main.py yandex clear-sync-calendar
python main.py yandex smoke-test
python main.py yandex integration-demo
```

## Типовые проблемы

### `python` не найден

Проверьте:

```powershell
py -3.11 --version
```

Если работает `py`, используйте его:

```powershell
py -3.11 -m venv .venv
```

Если не работает и `py`, установите Python 3.11+ и добавьте его в `PATH`.

### PowerShell не активирует `.venv`

Выполните:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Потом снова:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Google пишет `Access blocked` или `403: access_denied`

Значит OAuth-приложение находится в testing-режиме, а ваш Google-аккаунт не добавлен в test users.

Нужно:

- добавить аккаунт в test users в Google Cloud Console;
- убедиться, что включен Google Calendar API;
- заново пройти `python main.py google auth-url`.

### Google token устарел или авторизация сломалась

Удалите локальный токен:

```powershell
Remove-Item data\google_token.json
```

Потом заново выполните:

```powershell
python main.py google auth-url
python main.py google auth-finish "FINAL_LOCALHOST_URL"
```

### Yandex не авторизуется

Проверьте `.env`:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru
YANDEX_USERNAME=Bebrono@yandex.ru
YANDEX_APP_PASSWORD=your_yandex_app_password
```

Важно: нужен пароль приложения, а не обычный пароль от почты.

### События не обновляются

Проверьте поле `updated_at`. Сервис считает более свежей ту копию, у которой `updated_at` новее.

Если поменять `title`, но оставить старый `updated_at`, синхронизация может решить, что событие не изменилось.

### Появились странные старые данные

Команда `demo` очищает рабочие JSON-файлы, базу и лог. Для чистой проверки можно просто запустить:

```powershell
python main.py demo
```

Если нужно вручную очистить реальные тестовые календари:

```powershell
python main.py google clear-sync-calendar
python main.py yandex clear-sync-calendar
```

## Что не нужно коммитить

Эти файлы локальные и не должны попадать в Git:

- `.env`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/sync.db`;
- `logs/sync.log`;
- `.venv/`;
- `.pytest_cache/`.

## Как в будущем заменить mock на реальные API

Главная логика находится в `SyncService` и работает только с интерфейсом `CalendarAdapter`.

Чтобы подключить новый календарь, нужно:

1. Создать новый adapter, например `OutlookCalendarAdapter`.
2. Реализовать методы:

```python
get_events()
create_event(event)
update_event(event_id, event)
delete_event(event_id)
```

3. Подключить adapter в bootstrap-конфигурации.
4. Не менять `SyncService`, потому что он не зависит от конкретного API.

Именно поэтому JSON-файлы, Google Calendar и Yandex Calendar могут работать через одну и ту же синхронизационную логику.
