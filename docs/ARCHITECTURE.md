# Архитектура проекта

Calendar Sync Service построен вокруг общей логики синхронизации и сменных календарных адаптеров.

## Основная идея

`SyncService` не знает, где физически хранится календарь. Он работает только с интерфейсом `CalendarAdapter`.

Поэтому один и тот же сервис умеет синхронизировать:

- JSON-файлы;
- Google Calendar API;
- Yandex Calendar через CalDAV;
- будущий Outlook Calendar adapter.

## Модель события

Все внешние события приводятся к модели `CalendarEvent`:

- `id`;
- `title`;
- `description`;
- `start_time`;
- `end_time`;
- `organizer`;
- `attendees`;
- `source_system`;
- `source_owner`;
- `status`;
- `updated_at`.

Адаптер отвечает за преобразование внешнего формата в `CalendarEvent` и обратно.

## Адаптеры

Каждый календарь реализует методы:

```python
get_events()
create_event(event)
update_event(event_id, event)
delete_event(event_id)
```

Текущие реализации:

- `FileCalendarAdapter` - JSON mock-календари;
- `GoogleCalendarAdapter` - реальный Google Calendar API;
- `YandexCalendarAdapter` - реальный Yandex Calendar через CalDAV.

## Защита от дублей

Для всех копий одного события используется общий `sync_group_id`.

Связи между внешними событиями хранятся в SQLite-таблице `event_mappings`:

- `sync_group_id`;
- `calendar_owner`;
- `calendar_system`;
- `external_event_id`;
- `is_original`;
- `last_synced_at`;
- `status`;
- `last_event_updated_at`.

Дополнительно в описание события добавляются технические метки:

```text
[SYNC_ID: sync_xxx]
[SOURCE: google]
```

При повторном запуске сервис видит, что событие уже относится к существующей группе, и не создает дубликаты.

## Логика синхронизации

1. Сервис читает события из всех адаптеров.
2. Находит или создает `sync_group_id`.
3. Внутри группы выбирает самую свежую копию по `updated_at`.
4. Если событие активное, обновляет или создает копии в остальных календарях.
5. Если событие удалено, распространяет статус `deleted`.
6. Обновляет SQLite mappings.
7. Пишет логи в консоль, `logs/sync.log` и таблицу `sync_logs`.

## Live demo

Команда:

```powershell
python main.py live-demo
```

использует реальные Google и Yandex тестовые календари одновременно.

Она не является отдельной бизнес-логикой. Это проверочный сценарий поверх того же `SyncService`, который:

- очищает тестовое состояние;
- создает события из разных источников;
- запускает синхронизацию;
- проверяет результат;
- печатает `LIVE DEMO PASSED`, если все сценарии прошли.

Визуальный режим:

```powershell
python main.py live-demo --visual
```

использует тот же сценарий, но выводит ссылки на календари и делает паузы после ключевых шагов.

Ручной режим:

```powershell
python main.py live-links --prepare
```

выводит ссылки на тестовые календари и инструкцию для ручного создания события с последующим запуском `python main.py sync --real-google --real-yandex`.
