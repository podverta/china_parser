import asyncio
import time
import urllib3
from celery import current_app
from services_app.celery_app import celery_app, logger, redis_client
from fetch_data.parsers import parsers


PARSER_TIMEOUT = 60  # Таймаут для завершения старого инстанса


@celery_app.task(bind=True, queue='akty_queue')
def check_and_start_parsers_akty(self, is_first_run: bool = False):
    check_and_start_parsers('FetchAkty', is_first_run)


@celery_app.task(bind=True, queue='fb_queue')
def check_and_start_parsers_fb(self, is_first_run: bool = False):
    check_and_start_parsers('FB', is_first_run)


@celery_app.task(bind=True, queue='akty_queue', max_retries=5, default_retry_delay=60)
def parse_some_data_akty(self, *args, **kwargs):
    _parse_some_data(self, 'FetchAkty', *args, **kwargs)


@celery_app.task(bind=True, queue='fb_queue', max_retries=5, default_retry_delay=60)
def parse_some_data_fb(self, *args, **kwargs):
    _parse_some_data(self, 'FB', *args, **kwargs)


@celery_app.task(bind=True, queue='akty_queue', max_retries=5, default_retry_delay=60)
def schedule_stop_previous_instance_akty(self, parser_name, previous_task_id):
    _schedule_stop_previous_instance(self, parser_name, previous_task_id)


@celery_app.task(bind=True, queue='fb_queue', max_retries=5, default_retry_delay=60)
def schedule_stop_previous_instance_fb(self, parser_name, previous_task_id):
    _schedule_stop_previous_instance(self, parser_name, previous_task_id)


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


def _schedule_stop_previous_instance(self, parser_name, previous_task_id):
    """
    Планирует остановку предыдущего инстанса парсера через минуту.

    :param self: Ссылка на текущий экземпляр задачи.
    :param parser_name: Имя класса парсера, который необходимо запустить.
    :param previous_task_id: ID предыдущего таска парсера.
    """
    try:
        logger.info(f"Запланирована остановка предыдущей задачи {previous_task_id} для парсера {parser_name} через {PARSER_TIMEOUT} секунд.")
        stop_task(previous_task_id)
        clear_task_metadata(previous_task_id)
        logger.info(f"Предыдущая задача {previous_task_id} для парсера {parser_name} остановлена.")
    except Exception as e:
        logger.error(f"Ошибка при остановке предыдущего инстанса парсера {parser_name}: {e}")
        self.retry(exc=e)


def _parse_some_data(self, parser_name, *args, **kwargs):
    parser = None
    try:
        logger.info(f"Запуск парсера {parser_name} с task_id {self.request.id}")

        # Получаем класс парсера по имени
        parser_class = parsers.get(parser_name)
        if not parser_class:
            raise ValueError(f"Парсер с именем {parser_name} не найден")

        # Удаляем `is_first_run` из kwargs, чтобы не передавать его в конструктор парсера
        kwargs.pop('is_first_run', None)

        # Передаем все оставшиеся аргументы в конструктор парсера
        parser = parser_class()


        asyncio.run(parser.run())
        logger.info(f"Парсер {parser_name} с task_id {self.request.id} успешно завершен.")

    except TypeError as e:
        logger.error(f"Ошибка при создании парсера {parser_name}: {e}")
        self.retry(exc=e)
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


def check_and_start_parsers(parser_name: str, is_first_run: bool = False):
    """
    Проверяет активные задачи для указанного парсера и запускает новую задачу, если она не работает.
    """
    logger.info(f"Запуск проверки активных задач парсера {parser_name}.")

    if is_first_run:
        logger.info(f"Первый запуск, удаление всех celery-task-meta ключей из Redis для парсера {parser_name}.")
        delete_celery_task_meta_keys()

    inspect = current_app.control.inspect()
    active_tasks = inspect.active()  # Получаем активные задачи

    parser_tasks = []
    for worker, tasks in active_tasks.items():
        for task in tasks:
            if task['name'] == f'services_app.tasks.parse_some_data_{parser_name.lower()}' and task['args'][0] == parser_name:
                parser_tasks.append(task)

    # Завершаем старые задачи, если их больше двух
    if len(parser_tasks) > 2:
        parser_tasks.sort(key=lambda x: x['time_start'])  # Сортируем по времени старта
        for task in parser_tasks[:-2]:
            stop_task(task['id'])
            logger.info(f"Старая задача {task['id']} для парсера {parser_name} была остановлена.")

    active_task_id = redis_client.get(f"active_parser_{parser_name}")
    if not active_task_id or is_first_run:
        logger.info(f"Активная задача для парсера {parser_name} не найдена, запуск новой задачи через 30 секунд.")
        if parser_name == 'FetchAkty':
            parse_some_data_akty.apply_async(args=(parser_name,), kwargs={'is_first_run': is_first_run})
        elif parser_name == 'FB':
            parse_some_data_fb.apply_async(args=(parser_name,), kwargs={'is_first_run': is_first_run})
    else:
        logger.info(f"Активная задача {active_task_id.decode()} для парсера {parser_name} найдена, запуск новой задачи не требуется.")