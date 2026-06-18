# Инструкция для проверяющего

Цель проверки: убедиться, что сервис реально синхронизирует события между Google Calendar, Yandex Calendar и локальными JSON-календарями.

Проверяющий не должен вручную редактировать события, JSON-файлы, `updated_at`, `.env` или OAuth-настройки. Основная проверка запускается одной командой.

## 1. Скачать проект

```powershell
git clone https://github.com/Bebrono/intec_calendar.git
cd intec_calendar
```

Если проект передан архивом, распакуйте его и откройте терминал в папке проекта.

## 2. Установить зависимости

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если PowerShell блокирует активацию:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Запустить live-проверку

```powershell
python main.py live-demo
```

Команда автоматически:

- очищает SQLite-базу и рабочие JSON-календари;
- очищает тестовый Google Calendar;
- очищает тестовый Yandex Calendar;
- создает событие в JSON Outlook manager и проверяет появление копий в Google/Yandex;
- обновляет событие и проверяет распространение изменений;
- помечает событие удаленным и проверяет удаление;
- создает событие в Google и проверяет синхронизацию в Yandex + JSON;
- создает событие в Yandex и проверяет синхронизацию в Google + JSON;
- повторно запускает синхронизацию и проверяет, что дубликаты не появились.

## 4. Как понять, что все сработало

Успешный финальный вывод:

```text
LIVE DEMO PASSED
- Google Calendar: create/update/delete OK
- Yandex Calendar: create/update/delete OK
- Google <-> Yandex sync OK
- Duplicate protection OK
```

Это означает:

- сервис смог создать, обновить и удалить событие через Google Calendar API;
- сервис смог создать, обновить и удалить событие через Yandex CalDAV;
- событие из Google дошло до Yandex и JSON-календарей;
- событие из Yandex дошло до Google и JSON-календарей;
- повторный запуск не создал дубликаты.

## 5. Если проверка не стартует

Если вывод начинается так:

```text
LIVE DEMO CANNOT START
```

значит на машине не подготовлены локальные доступы к тестовым Google/Yandex календарям.

В этом случае проверяющему не нужно чинить проект самому. Нужно передать сообщение владельцу проекта: оно прямо укажет, какого локального файла или секрета не хватает.

Минимально для подготовленной машины нужны локальные файлы доступа, которые не лежат в Git:

- `.env` для Yandex;
- `data/google_token.json` для Google.

Google OAuth client файл `client_secret_*.json` тоже не хранится в репозитории. Он нужен только владельцу проекта, если потребуется заново пройти Google OAuth.

## 6. Дополнительная локальная проверка без API

Если нужно проверить только бизнес-логику без внешних календарей:

```powershell
python main.py demo
```

Эта команда работает только с JSON-файлами и не требует Google/Yandex доступов.

## 7. Автотесты

```powershell
pytest
```

Ожидаемый результат: все тесты проходят со статусом `passed`.
