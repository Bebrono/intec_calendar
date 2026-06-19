# Инструкция для проверяющего

Цель проверки: убедиться, что сервис синхронизирует события между Google
Calendar, двумя Yandex Calendar аккаунтами и локальным JSON mock-календарем
Outlook manager.

## 1. Подготовка проекта

Откройте терминал в папке проекта. На Windows это можно сделать из Проводника:
откройте папку проекта, кликните правой кнопкой по пустому месту и выберите
`Открыть в Терминале` / `Open in Terminal`.

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

## 2. Локальные файлы

Положите в корень проекта два файла от владельца проекта:

```text
credentials.json
.env
```

`credentials.json` нужен для Google OAuth. `.env` содержит Yandex логины и
пароли приложений.

## 3. Google авторизация

```powershell
python main.py google auth-url
```

Откройте ссылку из вывода под своей Gmail-почтой, разрешите доступ и скопируйте
финальный URL из адресной строки:

```text
http://localhost/?state=...&code=...&scope=...
```

Завершите авторизацию:

```powershell
python main.py google auth-finish "http://localhost/?state=...&code=...&scope=..."
```

## 4. Подготовка календарей

```powershell
python main.py live-links --prepare
```

Команда создает или находит тестовый Google календарь, два Yandex календаря,
очищает их и печатает ссылки для ручной проверки.

## 5. Автоматическая live-проверка

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

## 6. Ручная проверка

Откройте два терминала в корне проекта.

В первом терминале:

```powershell
python main.py watch
```

Во втором терминале:

```powershell
python main.py live-links
```

Проверочный сценарий:

1. Создать событие в Google Calendar.
2. Подождать до 10 секунд.
3. Проверить, что событие появилось у `developer_1`, `leader` и в JSON Outlook.
4. Изменить название или время события.
5. Проверить, что изменение разошлось всем участникам.
6. Удалить событие.
7. Проверить, что событие исчезло у остальных.
8. Повторить тот же сценарий из Yandex `developer_1` или `leader`.

## 7. Если проверка не стартует

Если вывод начинается с `LIVE DEMO CANNOT START` или `WATCH CANNOT START`,
значит не хватает `credentials.json`, Google авторизации или данных в `.env`.
Подробная подготовка Yandex паролей описана в `docs/SECRETS_SETUP.md`.

Логи пишутся в `logs/sync.log`, служебные записи синхронизации - в
`data/sync.db`.
