#!/bin/bash

# Загрузка переменных окружения из .env файла
source /var/www/data/www/backend/china_parser/.env

# Запуск задачи check_and_start_parsers
/var/www/data/www/backend/china_parser/.venv/bin/celery -A services_app.celery_app call services_app.tasks.check_and_start_parsers --args='[true]'
