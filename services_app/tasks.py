import os
import asyncio
import time
from redis import Redis
from celery import current_app
from services_app.celery_app import celery_app, logger
from fetch_data.parsers import parsers

redis_client = Redis.from_url(os.getenv('REDIS_URL'))

PARSER_TIMEOUT = 60  # Таймаут для завершения старого инстанса


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def schedule_stop_previous_instance(self, parser_name, previous_task_id):
    """
    Планирует остановку предыдущего инстанса парсера через минуту.

    :param self: Ссылка на текущий экземпляр задачи.
    :param parser_name: Имя класса парсера, который необходимо запустить.
    :param previous_task_id: ID предыдущего таска парсера.
    """
    try:
        time.sleep(PARSER_TIMEOUT)
        current_app.control.revoke(previous_task_id, terminate=True)
        logger.info(f"Previous instance of parser {parser_name} with task_id {previous_task_id} stopped.")
    except Exception as e:
        logger.error(f"Ошибка при остановке предыдущего инстанса парсера {parser_name}: {e}")
        self.retry(exc=e)


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def parse_some_data(self, parser_name, *args, **kwargs):
    """
    Запуск парсера для обработки данных.

    :param self: Ссылка на текущий экземпляр задачи.
    :param parser_name: Имя класса парсера, который необходимо запустить.
    :param args: Позиционные аргументы для инициализации парсера.
    :param kwargs: Именованные аргументы для инициализации парсера.
    """
    try:
        # Получаем класс парсера по имени
        parser_class = parsers.get(parser_name)
        if not parser_class:
            raise ValueError(f"Парсер с именем {parser_name} не найден")

        # Создаем экземпляр парсера и запускаем его
        parser = parser_class(*args, **kwargs)
        asyncio.run(parser.run())
    except Exception as e:
        logger.error(f"Ошибка при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
