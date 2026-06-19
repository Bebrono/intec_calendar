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

## Настройка прграммы

Все команды запускаются в корне проекта, то есть в папке, где лежит `main.py`.

1. Склонировать проект и поставить зависимости:

```powershell
git clone https://github.com/Bebrono/intec_calendar.git
cd intec_calendar
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

## Подключение Google аккаунта.
2. Положить в корень проекта два файл от владельца проекта:

```text
credentials.json
```

`credentials.json` нужен для Google OAuth.

3. Авторизовать Google под своей почтой:

```powershell
python main.py google auth-url
```

Откройте ссылку из вывода в браузере под своей Gmail-почтой, разрешите доступ к
календарю и скопируйте финальный URL из адресной строки. Он выглядит примерно
так:

```text
http://localhost/?state=...&code=...&scope=...
```

Если браузер показывает ошибку подключения к `localhost`, это нормально: код уже
есть в адресной строке.

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
```

## Как получить Yandex доступы

Для каждого Yandex аккаунта, который участвует в проверке:

1. Открыть <https://id.yandex.ru/>.
2. Слева открыть `Безопасность`.
3. Внизу страницы открыть `Пароли приложений`.
4. Выбрать тип приложения `Календарь`.
5. Ввести любое название, например `calendar-sync-review`.
6. Скопировать созданный пароль приложения.
7. Отправить владельцу проекта почту Yandex аккаунта и этот пароль приложения.

Владелец проекта вернет готовый `.env`. Его нужно положить в корень проекта,
рядом с `main.py` и `credentials.json`.

4. Подготовить чистые тестовые календари и получить ссылки:

```powershell
python main.py live-links --prepare
```

Команда создает или находит тестовый Google календарь, два Yandex календаря,
очищает их и сохраняет локальные config-файлы в `data/`.

5. Запустить live-демо как автотест:

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

6. Проверить синхронизацию руками.

Откройте два терминала в корне проекта. В первом запустите постоянную
синхронизацию:

```powershell
python main.py watch
```

Во втором выведите ссылки:

```powershell
python main.py live-links
```

Откройте ссылку Google Calendar и `https://calendar.yandex.ru/` для нужных
Yandex аккаунтов. Создайте, измените или удалите событие в Google/Yandex и
подождите до 10 секунд. Изменение должно появиться у остальных участников и в
`data/output/outlook_manager.json`.
## Что передать проверяющему

Проверяющему нужны только эти файлы:

- `credentials.json`;
- `.env`.

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
- `docs/SECRETS_SETUP.md` - подготовка `credentials.json` и `.env`.
- `docs/ARCHITECTURE.md` - краткое описание архитектуры.
- Google Calendar API Python quickstart:
  <https://developers.google.com/workspace/calendar/api/quickstart/python>
- Google OAuth consent и test users:
  <https://developers.google.com/workspace/guides/configure-oauth-consent>
- Yandex app passwords:
  <https://yandex.com/support/id/authorization/app-passwords.html>
