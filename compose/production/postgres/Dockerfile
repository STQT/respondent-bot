FROM docker.io/postgres:16

# Устанавливаем PgBouncer
RUN apt-get update && apt-get install -y pgbouncer

# Создаем пользователя pgbouncer
RUN useradd -r -s /bin/bash pgbouncer

# Создаем конфигурацию PgBouncer
RUN mkdir -p /etc/pgbouncer
COPY compose/production/postgres/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini
COPY compose/production/postgres/userlist.txt /etc/pgbouncer/userlist.txt

# Устанавливаем права доступа
RUN chown -R pgbouncer:pgbouncer /etc/pgbouncer

# Копируем скрипт запуска
COPY compose/production/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*

# Настройки PostgreSQL
RUN echo "max_connections = 300" >> /var/lib/postgresql/data/postgresql.conf

# Перемещаем скрипты
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

# Копируем скрипт запуска PgBouncer
COPY compose/production/postgres/start-pgbouncer.sh /usr/local/bin/start-pgbouncer.sh
RUN chmod +x /usr/local/bin/start-pgbouncer.sh

# Открываем порт PgBouncer
EXPOSE 5432 6432
