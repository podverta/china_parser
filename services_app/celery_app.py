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
    'run_fetch_akty': {
        'task': 'services_app.tasks.parse_some_data',
        'schedule': crontab(minute=3, hour='*/3'),
        'args': ('FetchAkty',),
    },
    'run_fb': {
        'task': 'services_app.tasks.parse_some_data',
        'schedule': crontab(minute=0, hour='*/1'),
        'args': ('FB',),
    },
    'check_and_start_parsers': {
        'task': 'services_app.tasks.check_and_start_parsers',
        'schedule': crontab(minute=0, hour='*'),  # Каждый час
    },
}
celery_app.conf.timezone = 'UTC'


# Инициализация Redis-клиента
redis_url = os.getenv('REDIS_URL')
redis_client = Redis.from_url(redis_url)
