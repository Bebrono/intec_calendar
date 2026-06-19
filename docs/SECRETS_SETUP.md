# Подготовка секретов и тестовых календарей

Этот документ нужен владельцу проекта и проверяющему, если он подключает свои
Google/Yandex аккаунты. В Git секреты не коммитятся.

## Что передать проверяющему

Если проверяющий должен запустить проект без самостоятельной настройки Google
Cloud/Yandex, передайте безопасным способом:

- `.env`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`.

Эти файлы нельзя коммитить в Git. Их можно передавать только безопасным способом,
если они нужны для проверки.

Не нужно передавать:

- `data/sync.db` - база будет создана автоматически;
- `logs/sync.log` - лог будет создан автоматически;
- `data/output/*.json` - тестовые JSON-календари создаются и очищаются командами проекта;
- `data/google_oauth_state.json` - временный файл незавершенного Google OAuth.

## Yandex: подключение пользователя

Yandex работает через CalDAV. Для каждого Yandex-участника нужен логин аккаунта
и пароль приложения. Обычный пароль от аккаунта не используйте.

Пример `.env`:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru

YANDEX_USERNAME=Bebrono@yandex.ru
YANDEX_APP_PASSWORD=developer_1_app_password

YANDEX_LEADER_USERNAME=siskosardelkin@yandex.ru
YANDEX_LEADER_APP_PASSWORD=leader_app_password
```

Соответствие переменных:

- `developer_1` читает `YANDEX_USERNAME` и `YANDEX_APP_PASSWORD`;
- `leader` читает `YANDEX_LEADER_USERNAME` и `YANDEX_LEADER_APP_PASSWORD`.

Если подключаете другого Yandex пользователя или заменяете пароль приложения,
удалите старые config-файлы:

```powershell
Remove-Item data\yandex_calendar_config.json -ErrorAction SilentlyContinue
Remove-Item data\yandex_leader_calendar_config.json -ErrorAction SilentlyContinue
```

Затем создайте тестовые календари заново:

```powershell
python main.py yandex --owner developer_1 create-sync-calendar
python main.py yandex --owner leader create-sync-calendar
```

Если нужно пересоздать/очистить все live-календари разом:

```powershell
python main.py live-links --prepare
```

## Google: готовый токен владельца

Если проверяющему передали `data/google_token.json` и
`data/google_calendar_config.json`, Google OAuth заново проходить не нужно.
Команды `python main.py live-demo`, `python main.py watch` и
`python main.py live-links` будут работать от имени аккаунта, который выдал этот
токен.

Важно: Google-токен не является логином/паролем и привязан к конкретному Google
аккаунту и OAuth client. Нельзя "подключить другого пользователя", просто
заменив Gmail в `.env`.

## Google: подключение другого Gmail к API

1. В Google Cloud создайте или откройте проект.
2. Включите Google Calendar API.
3. Настройте OAuth consent screen. Если приложение в режиме Testing, добавьте
   Gmail проверяющего в Test users.
4. Создайте OAuth client типа Desktop app.
5. Скачайте JSON клиента и положите в корень проекта одним из имен:

```text
credentials.json
```

или:

```text
client_secret_*.json
```

6. Удалите старое локальное состояние Google:

```powershell
Remove-Item data\google_token.json -ErrorAction SilentlyContinue
Remove-Item data\google_oauth_state.json -ErrorAction SilentlyContinue
Remove-Item data\google_calendar_config.json -ErrorAction SilentlyContinue
```

7. Сгенерируйте ссылку OAuth:

```powershell
python main.py google auth-url
```

8. Откройте ссылку под нужным Gmail и разрешите доступ к календарю. Приложение
   просит scope `https://www.googleapis.com/auth/calendar` и
   `https://www.googleapis.com/auth/calendar.events`.

9. После разрешения Google перенаправит на URL вида:

```text
http://localhost/?state=...&code=...&scope=...
```

Если браузер показывает ошибку подключения к `localhost`, это нормально: локальный
сервер не поднимается, а код авторизации уже находится в адресной строке.
Скопируйте весь URL и выполните:

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
python main.py google create-sync-calendar
```

## Google: другой человек только редактирует календарь

Если другому человеку нужно вручную создавать/изменять/удалять события в уже
созданном Google тестовом календаре, отдельный API-токен ему не нужен.

Владелец Google календаря должен открыть Google Calendar, найти календарь
`Calendar Sync Service Test`, поделиться им с Gmail проверяющего и выдать право
`Make changes to events` / `Вносить изменения в мероприятия`.

## Подготовка тестовых календарей

Основная команда:

```powershell
python main.py live-links --prepare
```

Она создает или находит тестовый Google календарь и два Yandex календаря,
очищает их и сохраняет локальные config-файлы в `data/`.

Финальная проверка:

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

## Официальные источники

- Google Calendar API Python quickstart:
  <https://developers.google.com/workspace/calendar/api/quickstart/python>
- Google OAuth consent и test users:
  <https://developers.google.com/workspace/guides/configure-oauth-consent>
- Google Calendar sharing:
  <https://support.google.com/calendar/answer/37082>
- Yandex app passwords:
  <https://yandex.com/support/id/authorization/app-passwords.html>
