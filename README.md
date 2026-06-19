# Calendar Sync Service

Python-сервис синхронизации календарей команды. Прототип объединяет:

- Google Calendar для `developer_2`;
- два Yandex Calendar через CalDAV: `developer_1` и `leader`;
- Outlook manager в виде локального JSON mock-календаря.

Сервис хранит единое состояние событий в SQLite, связывает копии через
`sync_group_id` и распространяет создание, обновление и удаление между всеми
участниками. Удаление является настоящим удалением из календарей; в БД остается
только служебная tombstone-запись, чтобы событие не создалось заново.

## Старт проверки

Все команды ниже запускаются в корне проекта, то есть в папке, где лежит
`main.py`. На Windows проще всего открыть терминал так: открыть папку проекта в
Проводнике, кликнуть правой кнопкой по пустому месту и выбрать
`Открыть в Терминале` или `Open in Terminal`.

1. Склонировать проект и установить зависимости:

```powershell
git clone https://github.com/Bebrono/intec_calendar.git
cd intec_calendar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если PowerShell не дает активировать окружение:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

2. Положить локальные доступы в проект.

Проверяющему нужны файлы и секреты, которые не коммитятся в Git:

- `.env` с паролями приложений Yandex;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`.

Если эти файлы передаются отдельно архивом, их нужно разложить по тем же путям
относительно корня проекта.

3. Запустить автоматическую live-проверку:

```powershell
python main.py live-demo
```

Успешный результат:

```text
LIVE DEMO PASSED
- Google Calendar: create/update/delete OK
- Yandex Calendar: create/update/delete OK
- Google <-> Yandex sync OK
- Duplicate protection OK
```

4. Для ручной проверки открыть два терминала.

В первом терминале запустить постоянную синхронизацию:

```powershell
python main.py watch
```

Во втором терминале вывести ссылки на тестовые календари:

```powershell
python main.py live-links
```

Если нужно сначала очистить тестовые календари и подготовить свежее состояние:

```powershell
python main.py live-links --prepare
```

Дальше можно открыть ссылки из `live-links`, создать, изменить или удалить
событие в Google/Yandex и подождать до 10 секунд. Изменение должно появиться у
остальных участников.

## Что проверять

- Создание события в Google появляется у обоих Yandex участников и в Outlook JSON.
- Создание события в Yandex появляется в Google, втором Yandex календаре и Outlook JSON.
- Обновление названия или времени у любого участника расходится всем.
- Удаление у любого участника удаляет событие у остальных.
- Повторный цикл синхронизации не создает дубликаты.

## Важные файлы

- `app/services/sync_service.py` - основная логика синхронизации.
- `app/storage/database.py` - SQLite-таблицы `synced_events`, `event_mappings`, `sync_logs`.
- `app/adapters/` - адаптеры Google, Yandex и JSON mock Outlook.
- `docs/REVIEWER_GUIDE.md` - короткая инструкция для проверяющего.
- `docs/SECRETS_SETUP.md` - какие локальные ключи нужны и куда их класть.
- `docs/ARCHITECTURE.md` - краткое описание архитектуры.

## Тесты

Локальные автотесты без ручной проверки календарей:

```powershell
pytest
```

Ожидаемый результат: все тесты проходят.
