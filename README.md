# Calendar Sync Service

Прототип сервиса синхронизации календарей на Python.

Проект показывает, как одно событие синхронизируется между участниками команды, даже если они используют разные календарные системы: Google Calendar, Yandex Calendar и JSON mock-календари вместо еще не подключенного Outlook API.

## Что готово

- Синхронизация создания, обновления и удаления событий.
- Защита от дублей и циклической синхронизации.
- SQLite-база соответствий между копиями событий.
- JSON mock-адаптеры для локальной демонстрации.
- Реальный Google Calendar API adapter.
- Реальный Yandex Calendar adapter через CalDAV.
- Проверочный сценарий Google + Yandex одной командой.
- Автотесты.

## Главная проверка

На подготовленной тестовой машине проверяющему нужна одна команда:

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

Эта команда сама очищает тестовые календари, создает события, проверяет синхронизацию Google + Yandex + JSON, проверяет обновления, удаления и защиту от дублей.

## Быстрый запуск

```powershell
git clone https://github.com/Bebrono/intec_calendar.git
cd intec_calendar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py live-demo
```

Если PowerShell не дает активировать окружение:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Важно про доступы

`live-demo` использует реальные тестовые календари Google и Yandex.

Секреты не лежат в публичном репозитории: `.env`, Google token и локальные calendar config файлы игнорируются Git. На проверочной машине они должны быть заранее подготовлены владельцем проекта.

Если доступов нет, команда завершится коротким сообщением:

```text
LIVE DEMO CANNOT START
- ...
```

Проверяющему не нужно вручную редактировать JSON, менять `updated_at`, создавать календари или разбираться в OAuth.

## Дополнительные команды

Локальная JSON-демонстрация без внешних API:

```powershell
python main.py demo
```

Обычная синхронизация с реальными Google и Yandex:

```powershell
python main.py sync --real-google --real-yandex
```

Автотесты:

```powershell
pytest
```

## Документация

- [Инструкция для проверяющего](docs/REVIEWER_GUIDE.md)
- [Архитектура проекта](docs/ARCHITECTURE.md)
- [Подготовка секретов и тестовых календарей](docs/SECRETS_SETUP.md)
