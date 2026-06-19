# Calendar Sync Service

Python-сервис синхронизации календарей команды. В live-режиме он связывает
четыре участника:

- `developer_1` - Yandex Calendar через CalDAV;
- `developer_2` - Google Calendar API;
- `manager` - локальный JSON mock для Outlook Calendar;
- `leader` - второй Yandex Calendar через CalDAV.

Сервис хранит единое каноническое состояние событий в SQLite. Любое создание,
изменение или удаление сначала фиксируется в БД, затем состояние из БД
проецируется во все календари. Удаление - hard delete из календарей; в SQLite
остается только служебная tombstone-запись, чтобы событие не создалось заново.

## Короткий маршрут проверки

Все команды ниже запускаются в корне проекта, то есть в папке, где лежит
`main.py`. На Windows откройте папку проекта в Проводнике, кликните правой
кнопкой по пустому месту и выберите `Открыть в Терминале` / `Open in Terminal`.

1. Склонировать проект и установить зависимости:

```powershell
git clone https://github.com/Bebrono/intec_calendar.git
cd intec_calendar
git switch codex/calendar-sync-canonical-db
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если PowerShell блокирует активацию окружения:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

2. Положить секреты и config-файлы.

Самый быстрый способ проверки - получить от владельца проекта архив с локальными
доступами и разложить файлы по тем же путям:

```text
.env
data/google_token.json
data/google_calendar_config.json
data/yandex_calendar_config.json
data/yandex_leader_calendar_config.json
```

3. Запустить live-демо как автотест:

```powershell
python main.py live-demo
```

Ожидаемый результат:

```text
LIVE DEMO PASSED
- Google Calendar: create/update/delete OK
- Yandex Calendar: create/update/delete OK
- Google <-> Yandex sync OK
- Duplicate protection OK
```

4. Проверить руками в календарях.

Откройте два терминала в корне проекта. В первом запустите постоянную
синхронизацию:

```powershell
python main.py watch
```

Во втором выведите ссылки на тестовые календари:

```powershell
python main.py live-links
```

Если нужно сначала очистить тестовые календари и пересоздать локальные config:

```powershell
python main.py live-links --prepare
```

Дальше откройте ссылки из `live-links`, создайте, измените или удалите событие в
Google/Yandex и подождите до 10 секунд. Изменение должно появиться у остальных
участников и в `data/output/outlook_manager.json`.

## Как подключаются аккаунты

### Yandex

Yandex подключается через логин и пароль приложения. Обычный пароль от аккаунта
использовать не нужно.

Пример `.env`:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru

YANDEX_USERNAME=developer-login@yandex.ru
YANDEX_APP_PASSWORD=developer_1_app_password

YANDEX_LEADER_USERNAME=leader-login@yandex.ru
YANDEX_LEADER_APP_PASSWORD=leader_app_password
```

После смены логина или пароля приложения удалите старые config-файлы:

```powershell
Remove-Item data\yandex_calendar_config.json -ErrorAction SilentlyContinue
Remove-Item data\yandex_leader_calendar_config.json -ErrorAction SilentlyContinue
```

Затем создайте тестовые календари заново:

```powershell
python main.py yandex --owner developer_1 create-sync-calendar
python main.py yandex --owner leader create-sync-calendar
```

Можно сделать то же самое одной командой для всех live-календарей:

```powershell
python main.py live-links --prepare
```

### Google

Google не подключается логином и паролем. Нужен OAuth-токен Google Calendar API.
Есть два рабочих сценария.

Сценарий A: проверяющий использует подготовленный доступ владельца проекта.

Владелец передает `data/google_token.json` и
`data/google_calendar_config.json`. Проверяющий ничего не авторизует заново:
`python main.py live-demo`, `python main.py watch` и `python main.py live-links`
используют уже выданный токен.

Сценарий B: другой человек подключает свой Google-аккаунт к API.

1. В Google Cloud включите Google Calendar API.
2. Настройте OAuth consent screen. Если приложение в режиме Testing, добавьте
   Gmail проверяющего в Test users.
3. Создайте OAuth client типа Desktop app.
4. Скачайте JSON клиента и положите в корень проекта как `credentials.json` или
   `client_secret_*.json`.
5. Удалите старые локальные файлы:

```powershell
Remove-Item data\google_token.json -ErrorAction SilentlyContinue
Remove-Item data\google_oauth_state.json -ErrorAction SilentlyContinue
Remove-Item data\google_calendar_config.json -ErrorAction SilentlyContinue
```

6. Пройдите OAuth:

```powershell
python main.py google auth-url
```

Откройте ссылку из вывода под нужным Gmail, разрешите доступ к календарю и
скопируйте финальный URL вида `http://localhost/?state=...&code=...&scope=...`.
Если браузер показывает ошибку подключения к localhost, это нормально: код уже в
адресной строке.

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
python main.py google create-sync-calendar
```

Если другому человеку нужно только руками редактировать уже созданный Google
тестовый календарь, новый API-токен не нужен. Достаточно открыть Google Calendar
в браузере, поделиться календарем с его Gmail и выдать право `Make changes to
events` / `Вносить изменения в мероприятия`.

## Что проверять

- Создание события в Google появляется у обоих Yandex участников и в Outlook JSON.
- Создание события в Yandex появляется в Google, втором Yandex календаре и Outlook JSON.
- Обновление названия или времени у любого участника расходится всем.
- Удаление у любого участника удаляет событие у остальных.
- Повторный цикл синхронизации не создает дубликаты.

## Что передать проверяющему

Если проверяющий должен запустить проект без самостоятельной настройки Google
Cloud/Yandex:

- архив с `.env`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`.

Если проверяющий сам проходит Google OAuth, вместо `data/google_token.json`
нужно передать OAuth client JSON (`credentials.json` или `client_secret_*.json`)
и добавить его Gmail в Test users, если Google Cloud приложение еще в Testing.

Не коммитьте в Git и передавайте только безопасным способом:

- `.env`;
- `credentials.json` или `client_secret_*.json`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`;
- `data/google_oauth_state.json`;

Не передавайте вообще:

- `data/sync.db`;
- `logs/*.log`;
- `.venv/`;
- `data/output/*.json`;

## Тесты

Локальные unit-тесты:

```powershell
pytest
```

или, если проект запускается через `uv`:

```powershell
uv run pytest
```

## Документация и источники

- `docs/REVIEWER_GUIDE.md` - короткая инструкция для проверяющего.
- `docs/SECRETS_SETUP.md` - подробная настройка секретов и OAuth.
- `docs/ARCHITECTURE.md` - краткое описание архитектуры.
- Google Calendar API Python quickstart:
  <https://developers.google.com/workspace/calendar/api/quickstart/python>
- Google OAuth consent и test users:
  <https://developers.google.com/workspace/guides/configure-oauth-consent>
- Google Calendar sharing:
  <https://support.google.com/calendar/answer/37082>
- Yandex app passwords:
  <https://yandex.com/support/id/authorization/app-passwords.html>
