#!/bin/bash

# Загрузка переменных окружения из .env файла
/var/www/api.parserchina.com/china_parser/.env

# Запуск задачи check_and_start_parsers с аргументом is_first_run=True
/var/www/api.parserchina.com/china_parser/.venv/bin/celery -A services_app.celery_app call services_app.tasks.check_and_start_parsers --args='[]' --kwargs='{"is_first_run": true}'