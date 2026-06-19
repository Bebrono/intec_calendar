# Подготовка секретов и тестовых календарей

Этот документ нужен владельцу проекта, который готовит машину для live-проверки.

Проверяющий не должен выполнять эти шаги вручную. Его команда:

```powershell
python main.py live-demo
```

## Что хранится локально

Эти файлы нужны для live-режима, но не коммитятся:

- `.env`;
- `client_secret_*.json`;
- `credentials.json`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/sync.db`;
- `logs/sync.log`.

Они перечислены в `.gitignore`.

## Google Calendar

OAuth client файл Google не должен лежать в репозитории. Если нужно заново пройти авторизацию, положите его локально в корень проекта:

```text
client_secret_*.json
```

или:

```text
credentials.json
```

Если Google OAuth еще не пройден:

```powershell
python main.py google auth-url
```

Откройте ссылку, разрешите доступ и скопируйте финальный redirect URL вида:

```text
http://localhost/?state=...&code=...&scope=...
```

Затем:

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
```

После этого появится локальный файл:

```text
data/google_token.json
```

Для обычного запуска `python main.py live-demo` проверяющему достаточно готового `data/google_token.json`. OAuth client файл нужен только для повторной авторизации.

Создать или переиспользовать тестовый календарь:

```powershell
python main.py google create-sync-calendar
```

Проверить прямой CRUD:

```powershell
python main.py google smoke-test
```

## Yandex Calendar

Нужен пароль приложения Yandex, не основной пароль от почты.

Создайте локальный `.env`:

```env
YANDEX_CALDAV_URL=https://caldav.yandex.ru
YANDEX_USERNAME=Bebrono@yandex.ru
YANDEX_APP_PASSWORD=your_yandex_app_password
```

Проверить авторизацию:

```powershell
python main.py yandex check-auth
```

Создать или переиспользовать тестовый календарь:

```powershell
python main.py yandex create-sync-calendar
```

Проверить прямой CRUD:

```powershell
python main.py yandex smoke-test
```

## Финальная проверка перед передачей

На подготовленной машине выполните:

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

Если команда проходит, проверяющий сможет запустить тот же сценарий без ручной настройки.

Для визуальной проверки:

```powershell
python main.py live-demo --visual
```

Для ручной проверки через браузер:

```powershell
python main.py live-links --prepare
```

Если проверка запускается на другой машине, передайте приватно:

- `.env`;
- `data/google_token.json`.

Файлы `data/google_calendar_config.json` и `data/yandex_calendar_config.json` можно не передавать: `live-demo` создаст или обновит тестовые календари сам.
