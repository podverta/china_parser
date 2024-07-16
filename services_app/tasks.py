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


def stop_task(task_id):
    try:
        current_app.control.revoke(task_id, terminate=True)
        logger.info(f"Задача {task_id} была остановлена.")
    except Exception as e:
        logger.error(f"Не удалось остановить задачу {task_id}: {e}")


def clear_task_metadata(task_id):
    try:
        celery_result = current_app.AsyncResult(task_id)
        celery_result.forget()
        logger.info(f"Метаданные задачи {task_id} удалены.")
    except Exception as e:
        logger.error(f"Не удалось удалить метаданные задачи {task_id}: {e}")


def delete_celery_task_meta_keys():
    try:
        keys = redis_client.keys("celery-task-meta-*")
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Удалены следующие ключи из Redis: {keys}")
        else:
            logger.info("Ключи для удаления не найдены.")
    except Exception as e:
        logger.error(f"Ошибка при удалении ключей celery-task-meta: {e}")


@celery_app.task
def check_and_start_parsers(is_first_run: bool = False):
    """
    Проверяет активные задачи парсеров и запускает их, если они не работают.
    """
    logger.info("Запуск проверки активных задач парсеров.")

    if is_first_run:
        logger.info(
            "Первый запуск, удаление всех celery-task-meta ключей из Redis.")
        delete_celery_task_meta_keys()

    inspect = current_app.control.inspect()
    active_tasks = inspect.active()  # Получаем активные задачи

    for parser_name in parsers.keys():
        parser_tasks = []

        for worker, tasks in active_tasks.items():
            for task in tasks:
                if task['name'] == 'services_app.tasks.parse_some_data' and \
                        task['args'][0] == parser_name:
                    parser_tasks.append(task)

        # Завершаем старые задачи, если их больше двух
        if len(parser_tasks) > 2:
            parser_tasks.sort(
                key=lambda x: x['time_start'])  # Сортируем по времени старта
            for task in parser_tasks[:-2]:
                stop_task(task['id'])
                logger.info(
                    f"Старая задача {task['id']} для парсера {parser_name} была остановлена.")

        active_task_id = redis_client.get(f"active_parser_{parser_name}")
        if not active_task_id or is_first_run:
            logger.info(
                f"Активная задача для парсера {parser_name} не найдена, запуск новой задачи через 30 секунд.")
            time.sleep(30)
            parse_some_data.apply_async(args=(parser_name,),
                                        kwargs={'is_first_run': is_first_run})
        else:
            logger.info(
                f"Активная задача {active_task_id.decode()} для парсера {parser_name} найдена, запуск новой задачи не требуется.")
