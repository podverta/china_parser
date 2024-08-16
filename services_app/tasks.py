import os
import asyncio
import time
import urllib3
from dotenv import load_dotenv
from redis import Redis
from celery import current_app
from services_app.celery_app import celery_app, logger, redis_client
from fetch_data.parsers import parsers


PARSER_TIMEOUT = 60  # Таймаут для завершения старого инстанса


def stop_task(task_id: str) -> None:
    """
    Останавливает задачу по её ID.

    :param task_id: ID задачи, которую нужно остановить.
    """
    try:
        current_app.control.revoke(task_id, terminate=True)
        logger.info(f"Задача {task_id} была остановлена.")
    except Exception as e:
        logger.error(f"Не удалось остановить задачу {task_id}: {e}")


def clear_task_metadata(task_id: str) -> None:
    """
    Удаляет метаданные задачи по её ID.

    :param task_id: ID задачи, метаданные которой нужно удалить.
    """
    try:
        celery_result = current_app.AsyncResult(task_id)
        celery_result.forget()
        logger.info(f"Метаданные задачи {task_id} удалены.")
    except Exception as e:
        logger.error(f"Не удалось удалить метаданные задачи {task_id}: {e}")


def delete_celery_task_meta_keys() -> None:
    """
    Удаляет все ключи метаданных задач Celery из Redis.
    """
    try:
        keys = redis_client.keys("celery-task-meta-*")
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Удалены следующие ключи из Redis: {keys}")
        else:
            logger.info("Ключи для удаления не найдены.")
    except Exception as e:
        logger.error(f"Ошибка при удалении ключей celery-task-meta: {e}")


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def parse_some_data(self, parser_name: str, *args, **kwargs) -> None:
    """
    Запуск парсера для обработки данных.

    :param self: Ссылка на текущий экземпляр задачи.
    :param parser_name: Имя класса парсера, который необходимо запустить.
    :param args: Позиционные аргументы для инициализации парсера.
    :param kwargs: Именованные аргументы для инициализации парсера.
    """
    parser = None
    try:
        logger.info(f"Запуск парсера {parser_name} с task_id {self.request.id}")

        parser_class = parsers.get(parser_name)
        if not parser_class:
            raise ValueError(f"Парсер с именем {parser_name} не найден")

        previous_task_id = redis_client.get(f"active_parser_{parser_name}")
        if previous_task_id:
            previous_task_id = previous_task_id.decode()
            if previous_task_id != self.request.id:
                logger.info(
                    f"Найдена предыдущая задача {previous_task_id} для парсера {parser_name}, остановка.")
                stop_task(previous_task_id)
                clear_task_metadata(previous_task_id)
            else:
                logger.info(f"Задача с тем же идентификатором {previous_task_id} уже активна.")

        redis_client.set(f"active_parser_{parser_name}", self.request.id)
        logger.info(f"Установлена активная задача {self.request.id} для парсера {parser_name} в Redis.")

        parser = parser_class(*args, **kwargs)
        asyncio.run(parser.run())
        logger.info(f"Парсер {parser_name} с task_id {self.request.id} успешно завершен.")

    except urllib3.exceptions.ProtocolError as e:
        logger.error(f"Ошибка протокола при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
    except Exception as e:
        logger.error(f"Ошибка при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
    finally:
        if parser:
            asyncio.run(parser.close())
        clear_task_metadata(self.request.id)


@celery_app.task
def check_and_start_parsers() -> None:
    """
    Проверяет активные задачи парсеров и запускает их в нужном порядке.
    """
    logger.info("Запуск проверки активных задач парсеров.")

    inspect = current_app.control.inspect()
    active_tasks = inspect.active()

    fb_tasks = [task for worker, tasks in active_tasks.items() for task in tasks if task['name'] == 'services_app.tasks.parse_some_data' and task['args'][0] == 'FB']

    if not fb_tasks:
        logger.info("Запуск новой задачи для FB.")
        parse_some_data.apply_async(args=('FB',))

    time.sleep(90)

    fetch_akty_tasks = [task for worker, tasks in active_tasks.items() for task in tasks if task['name'] == 'services_app.tasks.parse_some_data' and task['args'][0] == 'FetchAkty']

    if not fetch_akty_tasks:
        logger.info("Запуск новой задачи для FetchAkty.")
        parse_some_data.apply_async(args=('FetchAkty',))


@celery_app.task
def restart_all_parsers() -> None:
    """
    Перезапускает все парсеры, останавливая их старые инстансы.
    """
    logger.info("Перезапуск всех парсеров и остановка старых инстансов.")

    parser_names = ['FB', 'FetchAkty']
    for parser_name in parser_names:
        previous_task_id = redis_client.get(f"active_parser_{parser_name}")
        if previous_task_id:
            previous_task_id = previous_task_id.decode()
            logger.info(f"Остановка предыдущей задачи {previous_task_id} для парсера {parser_name}.")
            stop_task(previous_task_id)
            clear_task_metadata(previous_task_id)

        logger.info(f"Запуск новой задачи для {parser_name}.")
        parse_some_data.apply_async(args=(parser_name,))
