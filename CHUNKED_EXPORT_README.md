# Chunked Export System - Параллельный экспорт Excel

## Обзор

Новая система chunked экспорта позволяет разбивать большие объемы данных на части и обрабатывать их параллельно, что значительно ускоряет процесс экспорта Excel файлов.

## Основные преимущества

- **Параллельная обработка**: Несколько частей обрабатываются одновременно
- **Быстрый доступ**: Готовые части можно скачивать по мере завершения
- **Устойчивость**: При ошибке в одной части остальные продолжают обрабатываться
- **Масштабируемость**: Легко обрабатывает большие объемы данных

## Как использовать

### 1. Через Django Admin

1. Перейдите в **Respondents** → **Chunked экспорт (параллельный)**
2. Выберите опрос и параметры фильтрации
3. Настройте параметры chunked экспорта:
   - **Размер части**: Количество записей в каждой части (рекомендуется 1000-2000)
   - **Максимальное количество частей**: Максимум частей для экспорта (рекомендуется 10)
4. Нажмите **"Запустить chunked экспорт"**

### 2. Программно

```python
from apps.polls.tasks import export_respondents_chunked_task
from apps.polls.models import ExportFile, Poll

# Создаем запись экспорта
export_file = ExportFile.objects.create(
    poll=poll,
    include_unfinished=False,
    filename="my_export_chunked.xlsx"
)

# Запускаем chunked экспорт
export_respondents_chunked_task.delay(
    export_file.id,
    chunk_size=1000,  # размер части
    max_chunks=10     # максимум частей
)
```

## Мониторинг прогресса

### В Django Admin

1. Перейдите в **Export Files** для просмотра основного экспорта
2. Нажмите на запись экспорта для просмотра деталей
3. В разделе **"Chunked экспорт"** видите:
   - Общее количество частей
   - Завершенных частей
   - Процент выполнения
4. В разделе **"Части экспорта"** видите все части с их статусами

### Программно

```python
from apps.polls.models import ExportFile

export_file = ExportFile.objects.get(id=export_file_id)

# Проверяем статус
print(f"Статус: {export_file.status}")
print(f"Прогресс: {export_file.get_progress_percentage()}%")
print(f"Завершено частей: {export_file.completed_chunks}/{export_file.total_chunks}")

# Получаем все части
chunks = export_file.chunks.all()
for chunk in chunks:
    print(f"Часть {chunk.chunk_number}: {chunk.status} - {chunk.rows_count} записей")
```

## Скачивание файлов

### Отдельные части

```python
# Получаем URL для скачивания части
chunk = ExportChunk.objects.get(id=chunk_id)
if chunk.status == 'completed':
    download_url = chunk.get_file_url()
    print(f"Скачать часть: {download_url}")
```

### Все части

```python
# Получаем все завершенные части
completed_chunks = export_file.chunks.filter(status='completed')
for chunk in completed_chunks:
    print(f"Часть {chunk.chunk_number}: {chunk.get_file_url()}")
```

## Настройка производительности

### Рекомендуемые параметры

| Размер данных | Размер части | Максимум частей | Ожидаемое время |
|---------------|--------------|-----------------|-----------------|
| < 10,000 записей | 1,000 | 10 | 2-5 минут |
| 10,000-50,000 записей | 1,500 | 15 | 5-10 минут |
| 50,000-100,000 записей | 2,000 | 20 | 10-20 минут |
| > 100,000 записей | 2,500 | 25 | 20+ минут |

### Настройка Celery

Для оптимальной производительности настройте Celery:

```python
# settings.py
CELERY_WORKER_CONCURRENCY = 4  # Количество параллельных воркеров
CELERY_TASK_TIME_LIMIT = 1800  # 30 минут максимум на задачу
CELERY_TASK_SOFT_TIME_LIMIT = 1500  # 25 минут мягкий лимит
```

## Устранение неполадок

### Части не завершаются

1. Проверьте логи Celery: `docker-compose logs celery`
2. Убедитесь, что воркеры запущены: `docker-compose up celery`
3. Проверьте доступность базы данных

### Ошибки памяти

1. Уменьшите размер части (chunk_size)
2. Увеличьте количество частей (max_chunks)
3. Проверьте доступную память сервера

### Медленная обработка

1. Увеличьте количество Celery воркеров
2. Оптимизируйте запросы к базе данных
3. Используйте SSD для временных файлов

## API Reference

### Модели

#### ExportFile
- `is_chunked`: Boolean - является ли экспорт chunked
- `total_chunks`: Integer - общее количество частей
- `completed_chunks`: Integer - завершенных частей
- `chunk_size`: Integer - размер части
- `get_progress_percentage()`: Float - процент выполнения

#### ExportChunk
- `export_file`: ForeignKey - основной экспорт
- `chunk_number`: Integer - номер части
- `status`: CharField - статус части
- `rows_count`: Integer - количество записей
- `get_file_url()`: String - URL для скачивания

### Задачи

#### export_respondents_chunked_task
- `export_file_id`: ID основного экспорта
- `chunk_size`: Размер части (по умолчанию 1000)
- `max_chunks`: Максимум частей (по умолчанию 10)

#### export_chunk_task
- `chunk_id`: ID части для обработки

#### check_export_completion
- `export_file_id`: ID основного экспорта для проверки завершения
