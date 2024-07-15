import os
import asyncio
import time
from dotenv import load_dotenv
from redis import Redis
from celery import current_app
from services_app.celery_app import celery_app, logger
from fetch_data.parsers import parsers


# Загрузка переменных окружения из .env файла
load_dotenv()

redis_client = Redis.from_url(os.getenv('REDIS_URL'))

PARSER_TIMEOUT = 1  # Таймаут для завершения старого инстанса


def stop_task(task_id):
    try:
        current_app.control.revoke(task_id, terminate=True)
        logger.info(f"Задача {task_id} была остановлена.")
    except Exception as e:
        logger.error(f"Не удалось остановить задачу {task_id}: {e}")


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def schedule_stop_previous_instance(self, parser_name, previous_task_id):
    """
    Планирует остановку предыдущего инстанса парсера через минуту.

    :param self: Ссылка на текущий экземпляр задачи.
    :param parser_name: Имя класса парсера, который необходимо запустить.
    :param previous_task_id: ID предыдущего таска парсера.
    """
    try:
        logger.info(
            f"Запланирована остановка предыдущей задачи {previous_task_id} для парсера {parser_name} через {PARSER_TIMEOUT} секунд.")
        time.sleep(PARSER_TIMEOUT)
        stop_task(previous_task_id)
        logger.info(
            f"Предыдущая задача {previous_task_id} для парсера {parser_name} остановлена.")
    except Exception as e:
        logger.error(
            f"Ошибка при остановке предыдущего инстанса парсера {parser_name}: {e}")
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
        logger.info(f"Запуск парсера {parser_name} с task_id {self.request.id}")

        # Получаем класс парсера по имени
        parser_class = parsers.get(parser_name)
        if not parser_class:
            raise ValueError(f"Парсер с именем {parser_name} не найден")

        # Остановка предыдущего инстанса
        previous_task_id = redis_client.get(f"active_parser_{parser_name}")
        if previous_task_id:
            previous_task_id = previous_task_id.decode()
            logger.info(
                f"Найдена предыдущая задача {previous_task_id} для парсера {parser_name}, планируется остановка.")
            # Запускаем таск для остановки предыдущего инстанса через минуту
            schedule_stop_previous_instance.apply_async(
                (parser_name, previous_task_id), countdown=1)
        else:
            logger.info(
                f"Предыдущая задача для парсера {parser_name} не найдена.")

        # Создаем новый инстанс парсера и запускаем его
        parser = parser_class(*args, **kwargs)
        asyncio.run(parser.run())
        logger.info(
            f"Парсер {parser_name} с task_id {self.request.id} успешно завершен.")

        # Сохраняем текущий task_id в Redis
        redis_client.set(f"active_parser_{parser_name}", self.request.id)
        logger.info(
            f"Установлена активная задача {self.request.id} для парсера {parser_name} в Redis.")

    except urllib3.exceptions.ProtocolError as e:
        logger.error(
            f"Ошибка протокола при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
    except Exception as e:
        logger.error(f"Ошибка при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
