# PgBouncer Production Setup

## Настройка PostgreSQL для Production

После запуска production PostgreSQL, выполните следующие команды:

### 1. Изменить метод аутентификации на MD5
```bash
# Подключиться к PostgreSQL
docker-compose -f docker-compose.production.yml exec postgres psql -U apps -d apps

# Изменить pg_hba.conf
sed -i 's/host all all all scram-sha-256/host all all all md5/' /var/lib/postgresql/data/pg_hba.conf

# Перезагрузить конфигурацию
SELECT pg_reload_conf();
```

### 2. Настроить шифрование паролей на MD5
```sql
-- Изменить метод шифрования паролей
ALTER SYSTEM SET password_encryption = 'md5';

-- Перезагрузить конфигурацию
SELECT pg_reload_conf();

-- Переустановить пароль пользователя apps
ALTER USER apps WITH PASSWORD 'apps';
```

### 3. Проверить настройки
```sql
-- Проверить метод шифрования
SHOW password_encryption;

-- Проверить хеш пароля (должен начинаться с md5)
SELECT usename, passwd FROM pg_shadow WHERE usename = 'apps';
```

## Проверка работы PgBouncer

### 1. Тест подключения
```bash
# Подключиться через PgBouncer
PGPASSWORD=apps psql -h localhost -p 6432 -U apps -d apps -c "SELECT 1;"
```

### 2. Проверить статистику
```bash
# Подключиться к базе pgbouncer для просмотра статистики
PGPASSWORD=apps psql -h localhost -p 6432 -U apps -d pgbouncer -c "SHOW POOLS;"
PGPASSWORD=apps psql -h localhost -p 6432 -U apps -d pgbouncer -c "SHOW STATS;"
```

## Production настройки

- **max_client_conn**: 2000 (вместо 1000 в local)
- **default_pool_size**: 50 (вместо 20 в local)
- **min_pool_size**: 10 (вместо 5 в local)
- **reserve_pool_size**: 10 (вместо 5 в local)
- **verbose**: 1 (вместо 2 в local)

## Мониторинг

Для мониторинга PgBouncer в production используйте:

```bash
# Логи PgBouncer
docker-compose -f docker-compose.production.yml logs pgbouncer

# Статистика подключений
PGPASSWORD=apps psql -h localhost -p 6432 -U apps -d pgbouncer -c "SHOW CLIENTS;"
PGPASSWORD=apps psql -h localhost -p 6432 -U apps -d pgbouncer -c "SHOW SERVERS;"
``` 