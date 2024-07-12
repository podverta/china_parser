import asyncio
from services_app.celery_app import celery_app, logger
from fetch_data.parsers import parsers


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
