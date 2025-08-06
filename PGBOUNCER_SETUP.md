# Настройка PgBouncer для балансировки запросов

## Что было сделано

1. **Создана конфигурация PgBouncer** для локальной и production среды
2. **Обновлены docker-compose файлы** для интеграции PgBouncer
3. **Настроены переменные окружения** для подключения через PgBouncer
4. **Созданы скрипты мониторинга** и документация

## Структура файлов

```
compose/
├── local/
│   └── pgbouncer/
│       ├── Dockerfile
│       ├── pgbouncer.ini
│       ├── userlist.txt
│       ├── monitor.sh
│       └── README.md
└── production/
    └── pgbouncer/
        ├── Dockerfile
        ├── pgbouncer.ini
        └── userlist.txt

.envs/
├── .local/
│   ├── .django (обновлен)
│   └── .postgres
└── .production/
    ├── .django (новый)
    └── .postgres (новый)
```

## Тестирование локальной среды

### 1. Запуск Docker

```bash
# Убедитесь, что Docker запущен
docker --version
```

### 2. Сборка и запуск PgBouncer

```bash
# Сборка образа PgBouncer
docker-compose -f docker-compose.local.yml build pgbouncer

# Запуск всех сервисов
docker-compose -f docker-compose.local.yml up -d

# Или только PgBouncer для тестирования
docker-compose -f docker-compose.local.yml up pgbouncer postgres
```

### 3. Проверка подключения

```bash
# Проверка статуса PgBouncer
./compose/local/pgbouncer/monitor.sh

# Прямое подключение к PgBouncer
psql -h localhost -p 6432 -U debug -d apps

# Проверка статистики
psql -h localhost -p 6432 -U debug -d apps -c "SHOW POOLS;"
psql -h localhost -p 6432 -U debug -d apps -c "SHOW STATS;"
```

### 4. Тестирование Django

```bash
# Запуск Django с PgBouncer
docker-compose -f docker-compose.local.yml up django

# Проверка логов
docker-compose -f docker-compose.local.yml logs django
```

## Production настройка

### 1. Переменные окружения

Создайте файлы `.envs/.production/.django` и `.envs/.production/.postgres` с production настройками.

### 2. Запуск production

```bash
# Сборка production образов
docker-compose -f docker-compose.production.yml build

# Запуск production
docker-compose -f docker-compose.production.yml up -d
```

### 3. Мониторинг production

```bash
# Проверка статуса
docker-compose -f docker-compose.production.yml ps

# Логи PgBouncer
docker-compose -f docker-compose.production.yml logs pgbouncer

# Подключение к production PgBouncer
psql -h localhost -p 6432 -U apps -d apps
```

## Конфигурация PgBouncer

### Локальная среда
- **Порт**: 6432
- **Пользователь**: debug
- **Пароль**: debug
- **Размер пула**: 20 соединений
- **Режим**: transaction

### Production среда
- **Порт**: 6432
- **Пользователь**: apps
- **Пароль**: apps
- **Размер пула**: 50 соединений
- **Режим**: transaction

## Преимущества PgBouncer

1. **Connection Pooling** - эффективное управление соединениями с БД
2. **Load Balancing** - распределение нагрузки между соединениями
3. **Performance** - быстрые соединения из пула
4. **Monitoring** - встроенная статистика и логирование
5. **Scalability** - поддержка большего количества одновременных запросов

## Troubleshooting

### Проблемы с подключением

1. **Docker не запущен**
   ```bash
   # Запустите Docker Desktop
   ```

2. **PgBouncer не запускается**
   ```bash
   # Проверьте логи
   docker-compose -f docker-compose.local.yml logs pgbouncer
   
   # Проверьте конфигурацию
   docker-compose -f docker-compose.local.yml exec pgbouncer cat /etc/pgbouncer/pgbouncer.ini
   ```

3. **Django не подключается к PgBouncer**
   ```bash
   # Проверьте переменную DATABASE_URL
   docker-compose -f docker-compose.local.yml exec django env | grep DATABASE
   
   # Проверьте подключение к PgBouncer
   docker-compose -f docker-compose.local.yml exec django psql $DATABASE_URL -c "SELECT 1;"
   ```

### Настройка размера пула

Для изменения размера пула отредактируйте `pgbouncer.ini`:

```ini
# Увеличить размер пула для высокой нагрузки
default_pool_size = 100
min_pool_size = 20
reserve_pool_size = 20
```

## Следующие шаги

1. **Протестируйте локальную среду** - убедитесь, что все работает корректно
2. **Настройте production** - создайте production переменные окружения
3. **Мониторинг** - настройте мониторинг PgBouncer в production
4. **Оптимизация** - настройте размеры пулов под вашу нагрузку 