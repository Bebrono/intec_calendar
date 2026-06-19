# Подготовка `credentials.json` и `.env`

В Git секреты не коммитятся. Для проверки проекта проверяющий получает только:

- `credentials.json`;
- `.env`.

Все остальные служебные файлы создаются локально после Google авторизации и
команды `python main.py live-links --prepare`.

## Google

Владелец проекта передает проверяющему файл:

```text
credentials.json
```

Файл нужно положить в корень проекта, рядом с `main.py`.

Если Google OAuth приложение находится в режиме Testing, владелец проекта должен
добавить Gmail проверяющего в Google Cloud OAuth Test users до запуска команд.

Проверяющий авторизуется под своей Gmail-почтой:

```powershell
python main.py google auth-url
```

Открыть ссылку из вывода, разрешить доступ к календарю и скопировать финальный
URL из адресной строки:

```text
http://localhost/?state=...&code=...&scope=...
```

Если браузер показывает ошибку подключения к `localhost`, это нормально: код
авторизации уже находится в адресной строке.

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
```

После этого появится локальный файл `data/google_token.json`. Его не нужно
пересылать владельцу проекта и не нужно коммитить.

## Yandex

Для каждого Yandex аккаунта, который участвует в проверке, проверяющий создает
пароль приложения:

1. Открыть <https://id.yandex.ru/>.
2. Слева открыть `Безопасность`.
3. Внизу страницы открыть `Пароли приложений`.
4. Выбрать тип приложения `Календарь`.
5. Ввести любое название, например `calendar-sync-review`.
6. Скопировать созданный пароль приложения.
7. Отправить владельцу проекта почту Yandex аккаунта и этот пароль приложения.

Владелец проекта готовит `.env` и отправляет его проверяющему.

Пример `.env`:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru

YANDEX_USERNAME=developer-login@yandex.ru
YANDEX_APP_PASSWORD=developer_1_app_password

YANDEX_LEADER_USERNAME=leader-login@yandex.ru
YANDEX_LEADER_APP_PASSWORD=leader_app_password
```

Файл `.env` нужно положить в корень проекта, рядом с `main.py` и
`credentials.json`.

## Подготовка календарей

После Google авторизации и добавления `.env` выполните:

```powershell
python main.py live-links --prepare
```

Команда создает или находит тестовый Google календарь и два Yandex календаря,
очищает их, сохраняет локальные config-файлы в `data/` и печатает ссылки.

## Что не передавать и не коммитить

- `data/google_token.json`;
- `data/google_oauth_state.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`;
- `data/sync.db`;
- `logs/*.log`;
- `.venv/`;
- `data/output/*.json`.

## Официальные источники

- Google Calendar API Python quickstart:
  <https://developers.google.com/workspace/calendar/api/quickstart/python>
- Google OAuth consent и test users:
  <https://developers.google.com/workspace/guides/configure-oauth-consent>
- Yandex app passwords:
  <https://yandex.com/support/id/authorization/app-passwords.html>
