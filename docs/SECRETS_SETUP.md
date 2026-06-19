# Подготовка секретов и тестовых календарей

Этот документ нужен владельцу проекта. Проверяющему обычно достаточно получить
готовые локальные файлы из раздела "Что передать проверяющему".

## Что передать проверяющему

Эти файлы не коммитятся в Git и передаются отдельно безопасным способом:

- `.env`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`.

Не нужно передавать:

- `data/sync.db` - база будет создана автоматически;
- `logs/sync.log` - лог будет создан автоматически;
- `data/output/*.json` - тестовые JSON-календари создаются и очищаются командами проекта.

## Yandex

Нужны пароли приложений Yandex, а не обычные пароли от почты.

Пример `.env`:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru

YANDEX_USERNAME=Bebrono@yandex.ru
YANDEX_APP_PASSWORD=developer_1_app_password

YANDEX_LEADER_USERNAME=siskosardelkin@yandex.ru
YANDEX_LEADER_APP_PASSWORD=leader_app_password
```

## Google

Если `data/google_token.json` уже подготовлен, проверяющему не нужно заново
проходить OAuth.

Если OAuth нужно пройти с нуля, положите в корень проекта Google OAuth client:

```text
client_secret_*.json
```

или:

```text
credentials.json
```

Далее:

```powershell
python main.py google auth-url
```

Откройте ссылку, разрешите доступ и скопируйте финальный redirect URL вида:

```text
http://localhost/?state=...&code=...&scope=...
```

Завершите авторизацию:

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
```

## Подготовка тестовых календарей

Основная команда:

```powershell
python main.py live-links --prepare
```

Она создает или находит тестовые Google/Yandex календари, очищает их и сохраняет
локальные config-файлы в `data/`.

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
