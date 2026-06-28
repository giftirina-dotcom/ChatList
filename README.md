# ChatList

Приложение для отправки одного промта в несколько нейросетей и сравнения ответов.

## Требования

- Python 3.11+
- Windows / Linux / macOS

## Установка

```powershell
cd c:\Work\ChatList
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Откройте `.env` и укажите API-ключи. Для OpenRouter:

```env
OPENROUTER_API_KEY=sk-or-v1-...
```

## Запуск

```powershell
python main.py
```

## Настройка моделей

При первом запуске в БД создаются **6 бесплатных моделей OpenRouter** (активны по умолчанию):

| Модель | API ID |
|--------|--------|
| Qwen3 Next 80B (free) | `qwen/qwen3-next-80b-a3b-instruct:free` |
| Gemma 4 31B (free) | `google/gemma-4-31b-it:free` |
| OpenAI: gpt-oss-20b (free) | `openai/gpt-oss-20b:free` |
| OpenAI: gpt-oss-120b (free) | `openai/gpt-oss-120b:free` |
| Nemotron 3 Nano 30B (free) | `nvidia/nemotron-3-nano-30b-a3b:free` |
| Llama 3.2 3B (free) | `meta-llama/llama-3.2-3b-instruct:free` |

Все используют `OPENROUTER_API_KEY`. Лимиты бесплатного tier OpenRouter: ~50 запросов/день (до ~1000/день после пополнения $10+).

Управление — вкладка **Модели**:

- **Имя** — отображаемое название
- **API URL** — endpoint (OpenRouter: `https://openrouter.ai/api/v1/chat/completions`)
- **API ID** — идентификатор модели (например `google/gemma-4-31b-it:free`)
- **Переменная .env** — имя переменной с ключом (`OPENROUTER_API_KEY`)

API-ключи хранятся только в `.env`, не в базе данных.

## Рабочий процесс

1. Введите промт на вкладке **Запрос** (или выберите из истории).
2. Нажмите **Отправить** — запрос уйдёт во все активные модели.
3. Отметьте нужные ответы чекбоксами.
4. Нажмите **Сохранить** — выбранные результаты попадут в БД.
5. Просмотр истории — вкладки **Промты** и **Результаты**.

## Сборка exe

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name ChatList --noconfirm main.py
```

Исполняемый файл: `dist\ChatList.exe`

## Структура проекта

| Файл | Назначение |
|------|------------|
| `main.py` | Точка входа |
| `gui.py` | Графический интерфейс |
| `db.py` | SQLite |
| `models.py` | Бизнес-логика |
| `network.py` | HTTP-запросы к API |
| `workers.py` | Фоновая отправка промтов |
| `export_utils.py` | Экспорт MD / JSON |
| `app_logger.py` | Логирование запросов |

## Документация

- [PROJECT.md](PROJECT.md) — спецификация
- [PLAN.md](PLAN.md) — план реализации
- [DATABASE.md](DATABASE.md) — схема БД
