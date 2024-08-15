#!/bin/bash

# Загрузка переменных окружения из .env файла
source /var/www/api.parserchina.com/china_parser/.env

# Запуск задачи check_and_start_parsers_akty с аргументом is_first_run=True
/var/www/api.parserchina.com/china_parser/.venv/bin/celery -A services_app.celery_app call services_app.tasks.check_and_start_parsers_akty --args='[true]'

# Запуск задачи check_and_start_parsers_fb с аргументом is_first_run=True
/var/www/api.parserchina.com/china_parser/.venv/bin/celery -A services_app.celery_app call services_app.tasks.check_and_start_parsers_fb --args='[true]'
