# Инструкция для проверяющего

Цель проверки: убедиться, что сервис синхронизирует события между Google
Calendar, двумя Yandex Calendar аккаунтами и локальным JSON mock-календарем
Outlook manager.

## 1. Подготовка проекта

Откройте терминал в папке проекта. На Windows это можно сделать из Проводника:
откройте папку проекта, кликните правой кнопкой по пустому месту и выберите
`Открыть в Терминале`.

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

## 2. Локальные доступы

В Git нет секретов. Владелец проекта должен передать отдельно:

- `.env`;
- `data/google_token.json`;
- `data/google_calendar_config.json`;
- `data/yandex_calendar_config.json`;
- `data/yandex_leader_calendar_config.json`.

Файлы нужно положить в те же относительные пути внутри проекта.

## 3. Автоматическая live-проверка

```powershell
python main.py live-demo
```

Команда очищает тестовые календари, создает события из разных источников,
проверяет создание, обновление, удаление и защиту от дублей.

Ожидаемый результат:

```text
LIVE DEMO PASSED
- Google Calendar: create/update/delete OK
- Yandex Calendar: create/update/delete OK
- Google <-> Yandex sync OK
- Duplicate protection OK
```

## 4. Ручная проверка

Откройте два терминала в корне проекта.

В первом терминале:

```powershell
python main.py watch
```

Во втором терминале:

```powershell
python main.py live-links
```

Если нужно сначала очистить тестовые календари:

```powershell
python main.py live-links --prepare
```

`live-links` покажет ссылку на Google Calendar и две строки для Yandex:
`developer_1` и `leader`. Для просмотра конкретного Yandex календаря нужно быть
авторизованным в соответствующем аккаунте или открыть календарь в отдельном
профиле браузера.

Проверочный сценарий:

1. Создать событие в Google Calendar.
2. Подождать до 10 секунд.
3. Проверить, что событие появилось у `developer_1`, `leader` и в JSON Outlook.
4. Изменить название или время события.
5. Проверить, что изменение разошлось всем участникам.
6. Удалить событие.
7. Проверить, что событие исчезло у остальных.
8. Повторить тот же сценарий из Yandex `developer_1` или `leader`.

## 5. Если проверка не стартует

Если вывод начинается с `LIVE DEMO CANNOT START` или `WATCH CANNOT START`,
значит не хватает локальных доступов. Проверьте файлы из раздела 2.

Логи пишутся в `logs/sync.log`, служебные записи синхронизации - в
`data/sync.db`.

## 6. Обычные автотесты

```powershell
pytest
```

Ожидаемый результат: все тесты проходят.
