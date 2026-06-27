# Схема базы данных ChatList

База данных: **SQLite**  
Файл по умолчанию: `chatlist.db`  
Доступ: только через модуль `db.py`.

API-ключи **не хранятся** в БД. В таблице `models` хранится имя переменной окружения; значение ключа читается из файла `.env`.

---

## ER-диаграмма (логическая модель)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   prompts   │       │   results   │       │   models    │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │◄──┐   │ id (PK)     │   ┌──►│ id (PK)     │
│ created_at  │   └───│ prompt_id   │   │   │ name        │
│ prompt      │       │ model_id    │───┘   │ api_url     │
│ tags        │       │ response    │       │ api_id      │
└─────────────┘       │ created_at  │       │ api_key_env │
                      └─────────────┘       │ is_active   │
                                            │ model_type  │
┌─────────────┐                             └─────────────┘
│  settings   │
├─────────────┤
│ key (PK)    │
│ value       │
└─────────────┘
```

---

## Таблица `prompts`

Хранит историю запросов пользователя.

| Поле        | Тип          | Ограничения              | Описание                              |
|-------------|--------------|--------------------------|---------------------------------------|
| `id`        | INTEGER      | PRIMARY KEY AUTOINCREMENT| Уникальный идентификатор              |
| `created_at`| TEXT         | NOT NULL                 | Дата и время создания (ISO 8601)      |
| `prompt`    | TEXT         | NOT NULL                 | Текст промта                          |
| `tags`      | TEXT         | NULL                     | Теги через запятую, например `code,test` |

**Индексы:**
- `idx_prompts_created_at` — сортировка по дате;
- `idx_prompts_tags` — опционально, для поиска по тегам.

**Пример записи:**

| id | created_at           | prompt              | tags    |
|----|----------------------|---------------------|---------|
| 1  | 2026-06-23T10:00:00  | Объясни asyncio     | python  |

---

## Таблица `models`

Справочник нейросетей и параметров подключения.

| Поле         | Тип     | Ограничения              | Описание                                           |
|--------------|---------|--------------------------|----------------------------------------------------|
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT| Уникальный идентификатор                           |
| `name`       | TEXT    | NOT NULL UNIQUE          | Отображаемое имя модели                            |
| `api_url`    | TEXT    | NOT NULL                 | URL endpoint API                                   |
| `api_id`     | TEXT    | NOT NULL                 | Идентификатор модели в API (например `gpt-4o-mini`)|
| `api_key_env`| TEXT    | NOT NULL                 | Имя переменной окружения с ключом (например `OPENAI_API_KEY`) |
| `is_active`  | INTEGER | NOT NULL DEFAULT 1       | 1 — участвует в отправке, 0 — отключена            |
| `model_type` | TEXT    | NULL                     | Тип API: `openai`, `deepseek`, `groq` и т.д.       |

**Индексы:**
- `idx_models_is_active` — быстрый выбор активных моделей.

**Пример записи:**

| id | name     | api_url                              | api_id      | api_key_env    | is_active | model_type |
|----|----------|--------------------------------------|-------------|----------------|-----------|------------|
| 1  | GPT-4o   | https://api.openai.com/v1/chat/completions | gpt-4o | OPENAI_API_KEY | 1         | openai     |
| 2  | DeepSeek | https://api.deepseek.com/v1/chat/completions | deepseek-chat | DEEPSEEK_API_KEY | 0    | deepseek   |

**Связь с `.env`:**

```env
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
```

---

## Таблица `results`

Постоянное хранение ответов, отмеченных пользователем для сохранения.

| Поле           | Тип     | Ограничения                        | Описание                          |
|----------------|---------|------------------------------------|-----------------------------------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT          | Уникальный идентификатор          |
| `prompt_id`    | INTEGER | NOT NULL, FK → `prompts.id`        | Ссылка на промт                   |
| `model_id`     | INTEGER | NOT NULL, FK → `models.id`         | Ссылка на модель                  |
| `response_text`| TEXT    | NOT NULL                           | Текст ответа нейросети            |
| `created_at`   | TEXT    | NOT NULL                           | Дата и время сохранения (ISO 8601)|

**Индексы:**
- `idx_results_prompt_id` — выборка результатов по промту;
- `idx_results_model_id` — выборка по модели;
- `idx_results_created_at` — сортировка по дате.

**Пример записи:**

| id | prompt_id | model_id | response_text        | created_at           |
|----|-----------|----------|----------------------|----------------------|
| 1  | 1         | 1        | Asyncio — это...     | 2026-06-23T10:05:00  |

---

## Таблица `settings`

Key-value хранилище настроек программы.

| Поле   | Тип  | Ограничения     | Описание              |
|--------|------|-----------------|-----------------------|
| `key`  | TEXT | PRIMARY KEY     | Ключ настройки        |
| `value`| TEXT | NOT NULL        | Значение настройки    |

**Примеры настроек:**

| key              | value   | Описание                          |
|------------------|---------|-----------------------------------|
| `request_timeout`| `30`    | Таймаут HTTP-запроса (секунды)    |
| `db_path`        | `chatlist.db` | Путь к файлу БД             |
| `log_requests`   | `1`     | Включить логирование запросов     |

---

## Временная таблица результатов (не в SQLite)

Используется **только в памяти** во время сеанса работы с текущим промтом. В БД не сохраняется.

Структура (Python dataclass / список словарей):

| Поле            | Тип    | Описание                              |
|-----------------|--------|---------------------------------------|
| `model_id`      | int    | ID модели из таблицы `models`         |
| `model_name`    | str    | Имя модели для отображения            |
| `response_text` | str    | Текст ответа или сообщение об ошибке  |
| `selected`      | bool   | Отмечен ли чекбокс для сохранения     |
| `error`         | str?   | Текст ошибки, если запрос не удался   |

**Жизненный цикл:**
1. Создаётся после нажатия «Отправить».
2. Очищается после «Сохранить» или при новом запросе.
3. Строки с `selected = True` переносятся в таблицу `results`.

---

## SQL: создание таблиц

```sql
CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    prompt     TEXT    NOT NULL,
    tags       TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    api_url     TEXT    NOT NULL,
    api_id      TEXT    NOT NULL,
    api_key_env TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    model_type  TEXT
);

CREATE TABLE IF NOT EXISTS results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id     INTEGER NOT NULL,
    model_id      INTEGER NOT NULL,
    response_text TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id)  REFERENCES models(id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prompts_created_at ON prompts(created_at);
CREATE INDEX IF NOT EXISTS idx_models_is_active    ON models(is_active);
CREATE INDEX IF NOT EXISTS idx_results_prompt_id   ON results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_results_model_id    ON results(model_id);
CREATE INDEX IF NOT EXISTS idx_results_created_at  ON results(created_at);
```

---

## Ограничения целостности

| Правило | Реализация |
|---------|------------|
| Удаление промта | `ON DELETE CASCADE` для `results.prompt_id` — результаты удаляются вместе с промтом |
| Удаление модели | `ON DELETE RESTRICT` — нельзя удалить модель, если есть сохранённые результаты |
| Активные модели | Выборка `SELECT * FROM models WHERE is_active = 1` |
| API-ключи | Только в `.env`, в БД — только `api_key_env` |

---

## Начальные данные (seed)

При первом запуске рекомендуется добавить:

**settings:**
```sql
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('request_timeout', '30'),
    ('db_path', 'chatlist.db'),
    ('log_requests', '0');
```

**models** (неактивные заглушки, пользователь активирует после настройки `.env`):
```sql
INSERT OR IGNORE INTO models (name, api_url, api_id, api_key_env, is_active, model_type) VALUES
    ('GPT-4o', 'https://api.openai.com/v1/chat/completions', 'gpt-4o', 'OPENAI_API_KEY', 0, 'openai'),
    ('DeepSeek Chat', 'https://api.deepseek.com/v1/chat/completions', 'deepseek-chat', 'DEEPSEEK_API_KEY', 0, 'deepseek');
```
