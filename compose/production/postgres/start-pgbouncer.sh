#!/bin/bash

# Создаем домашнюю директорию для pgbouncer
mkdir -p /home/pgbouncer
chown pgbouncer:pgbouncer /home/pgbouncer

# Запускаем PgBouncer в фоне
su pgbouncer -c "pgbouncer /etc/pgbouncer/pgbouncer.ini" &

# Ждем запуска PgBouncer
sleep 5

# Запускаем PostgreSQL (стандартный entrypoint)
exec docker-entrypoint.sh postgres 