import os
import sys
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from redis import Redis
from app.logging import setup_logger

# Загрузка переменных окружения из .env файла
load_dotenv()

# Добавьте корневой каталог проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Инициализация Celery
celery_app = Celery('services_app',
                    broker=os.getenv('REDIS_URL'),
                    backend=os.getenv('REDIS_URL'))

# Укажите путь к задачам
celery_app.autodiscover_tasks(['services_app'])

# Настройка логирования
logger = setup_logger('celery', 'celery.log')

# Настройка расписания задач
celery_app.conf.beat_schedule = {
    'check_and_start_parsers_akty': {
        'task': 'services_app.tasks.check_and_start_parsers_akty',
        'schedule': crontab(minute=5, hour='*'),
    },
    'check_and_start_parsers_fb': {
        'task': 'services_app.tasks.check_and_start_parsers_fb',
        'schedule': crontab(minute=5),
    },
    'run_fetch_akty': {
        'task': 'services_app.tasks.parse_some_data_akty',
         'schedule': crontab(minute=4, hour='*/3'),
    },
    'run_fb': {
        'task': 'services_app.tasks.parse_some_data_fb',
        'schedule': crontab(minute=21, hour='*/1'),
    },
}
celery_app.conf.timezone = 'UTC'

celery_app.conf.task_routes = {
    'services_app.tasks.check_and_start_parsers_akty': {'queue': 'akty_queue'},
    'services_app.tasks.check_and_start_parsers_fb': {'queue': 'fb_queue'},
    'services_app.tasks.parse_some_data_akty': {'queue': 'akty_queue'},
    'services_app.tasks.parse_some_data_fb': {'queue': 'fb_queue'},
    'services_app.tasks.schedule_stop_previous_instance_akty': {
        'queue': 'akty_queue'},
    'services_app.tasks.schedule_stop_previous_instance_fb': {
        'queue': 'fb_queue'},
}

# Инициализация Redis-клиента
redis_url = os.getenv('REDIS_URL')
redis_client = Redis.from_url(redis_url)
