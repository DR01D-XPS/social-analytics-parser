# Social Analytics Parser (VK / Telegram / MAX)

Веб-приложение с тёмной темой для сбора и аналитики:
- статистики постов,
- притока/оттока аудитории,
- графиков с фильтрами периода,
- экспорта CSV,
- ручной и плановой синхронизации источников.

## Что реализовано

- Backend: FastAPI + SQLite + SQLAlchemy + APScheduler.
- Коннекторы по единому интерфейсу для `vk`, `telegram`, `max`.
- Два режима источников:
  - `mock` - работает сразу, генерирует реалистичные данные.
  - `http`:
    - для `vk` без `api_base_url` - прямой режим официального VK API (реальные данные);
    - для `telegram`/`max` (и при заданном URL для `vk`) - интеграция через внешний adapter API.
- API:
  - `GET /api/accounts`, `POST /api/accounts`, `PATCH /api/accounts/{id}`, `DELETE /api/accounts/{id}`
  - `POST /api/sync/run-all`, `POST /api/sync/run/{account_id}`
  - `GET /api/reports/overview`
  - `GET /api/reports/overview.csv`
- Frontend:
  - `/` - Dashboard с KPI, графиками и таблицей топ-постов.
  - `/sources` - управление источниками.

## Запуск

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. (Опционально) скопировать `.env.example` в `.env` и поменять параметры.

3. Запустить сервер:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Открыть:
- `http://127.0.0.1:8000/` - дашборд
- `http://127.0.0.1:8000/sources` - источники

## Реальные данные VK (без адаптера)

На странице `/sources` создайте источник с параметрами:
- `Платформа`: `VK`
- `Внешний ID`: shortname сообщества (например `chebylo`) или числовой ID
- `Режим источника`: `http-адаптер`
- `Базовый URL API`: оставить пустым
- `API токен`: токен VK (обязательно)

После создания нажмите `Синхр.` в таблице источников.

Ограничения:
- Для постов/метрик используются методы VK API (`wall.get`, `wall.getById`, `groups.getById`).
- Приток/отток берется из `stats.get`, если у токена есть нужные права и доступ к статистике сообщества.
- Если `stats.get` недоступен, приток/отток будут `0`, но посты и просмотры продолжат синхронизироваться.

## Формат adapter API для режима `http`

### `GET {base_url}/posts?since=<ISO8601>`

```json
{
  "items": [
    {
      "external_id": "post-123",
      "published_at": "2026-03-01T10:00:00+00:00",
      "content_preview": "text",
      "url": "https://..."
    }
  ]
}
```

### `POST {base_url}/post-metrics`

Request:

```json
{
  "posts": [
    {
      "external_id": "post-123",
      "published_at": "2026-03-01T10:00:00+00:00",
      "url": "https://..."
    }
  ]
}
```

Response:

```json
{
  "items": [
    {
      "post_external_id": "post-123",
      "captured_at": "2026-03-12T11:22:00+00:00",
      "views": 1200,
      "reactions": 90,
      "comments": 17,
      "reposts": 8,
      "reach": 1450
    }
  ]
}
```

### `GET {base_url}/audience`

```json
{
  "captured_at": "2026-03-12T11:22:00+00:00",
  "total_subscribers": 15230,
  "inflow": 54,
  "outflow": 39
}
```

## Примечание

Реальные API VK/Telegram/MAX различаются по правам и доступности статистики. В проекте это решено adapter-слоем: под каждый источник можно подключить собственный сервис, который приводит данные к единому контракту.
