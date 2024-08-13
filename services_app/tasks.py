import json
import asyncio
import time
import urllib3
from celery import current_app
from services_app.celery_app import celery_app, logger, redis_client
from fetch_data.parsers import parsers
from transfer_data.redis_client import RedisClient


PARSER_TIMEOUT = 60  # Таймаут для завершения старого инстанса


async def check_and_init_translate_cash(redis_client: RedisClient):
    """
    Проверяет наличие ключа 'translate_cash' в Redis и инициализирует его, если он отсутствует.

    Args:
        redis_client (RedisClient): Клиент Redis для выполнения операций.
    """
    # Проверяем, существует ли ключ 'translate_cash' в Redis
    existing_data = await redis_client.get_data('translate_cash')

    if existing_data is None:
        logger.info(
            "Ключ 'translate_cash' не найден в Redis, инициализация значений.")
        translate_cash = {
            "骑士": "knight",
            "海军": "navy",
            "海鸟(女)": "seagull (female)",
            "火烈鸟(女)": "firebird (female)",
            "突袭者": "raider",
            "燕子(女)": "swallow (female)",
            "巨鸭(女)": "giant duck (female)",
            "乌兰乌德": "ulan ude",
            "车里雅宾斯克": "chelyabinsk",
            "枪手": "shooter",
            "卡卢加(女)": "kaluga (female)",
            "伊万诺沃(女)": "ivanovo (female)",
            "斯塔夫罗波尔": "stavropol",
            "乌发": "ufa",
            "奔萨(女)": "penza (female)",
            "科斯特罗马(女)": "kostroma (female)",
            "彼尔姆": "perm",
            "沃罗涅日": "voronezh",
            "伏尔加": "volga",
            "唐": "tang",
            "奥卡": "oka",
            "叶尼塞": "yenisei",
            "克拉斯诺亚尔斯克": "krasnoyarsk",
            "奥伦堡(女)": "orenburg (female)",
            "乌拉尔": "ural",
            "西伯利亚": "siberia",
            "阿斯佩塞特": "aspect",
            "埃森图基": "essentuki",
            "库尔斯克(女)": "kursk (female)",
            "沃洛格达(女)": "vologda (female)",
            "夸察加": "kachgaga",
            "库班": "kuban",
            "伊尔库茨克": "irkutsk",
            "克麦罗沃": "kemerovo",
            "艾斯贝斯特": "asbest",
            "叶先图基": "yesentuk",
            "萨马拉(女)": "samara (female)",
            "叶卡捷琳堡(女)": "yekaterinburg (female)",
            "莫斯科": "moscow",
            "索契": "sochi",
            "迈科普": "maykop",
            "纳尔奇克": "nalchik",
            "圣彼得堡": "saint petersburg",
            "喀山": "kazan",
            "别尔哥罗德": "belgorod",
            "萨拉托夫": "saratov",
            "欧姆斯克": "omsk",
            "赤塔": "chita",
            "鄂木斯克": "omsk",
            "巴尔瑙尔": "barnaul",
            "苏尔古特": "surgut",
            "伏尔加格勒(女)": "volgograd (female)",
            "秋明(女)": "tyumen (female)",
            "哈巴罗夫斯克": "khabarovsk",
            "加里宁格勒": "kaliningrad",
            "新西伯利亚": "novosibirsk",
            "符拉迪沃斯托克": "vladivostok",
            "加时赛": "overtime",
            "等待加时": "waiting for overtime",
            "第一节": "first quarter",
            "第二节": "second quarter",
            "第三节": "third quarter",
            "第四节": "fourth quarter",
            "半场": "halftime",
            "全场结束": "full-time",
            "即将开赛": "about to start"
        }
        # Сохраняем словарь в Redis
        await redis_client.set_data('translate_cash', json.dumps(translate_cash,
                                                                 ensure_ascii=False))
    else:
        logger.info(
            "Ключ 'translate_cash' уже существует в Redis, инициализация не требуется.")

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
            f"Запланирована остановка предыдущей задачи {previous_task_id} "
            f"для парсера {parser_name} через {PARSER_TIMEOUT} секунд.")
        time.sleep(PARSER_TIMEOUT)
        stop_task(previous_task_id)
        clear_task_metadata(previous_task_id)
        logger.info(
            f"Предыдущая задача {previous_task_id} для парсера "
            f"{parser_name} остановлена.")
    except Exception as e:
        logger.error(
            f"Ошибка при остановке предыдущего инстанса"
            f" парсера {parser_name}: {e}")
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
    parser = None
    try:
        logger.info(f"Запуск парсера {parser_name} с task_id {self.request.id}")

        # Получаем класс парсера по имени
        parser_class = parsers.get(parser_name)
        if not parser_class:
            raise ValueError(f"Парсер с именем {parser_name} не найден")

        # Остановка предыдущего инстанса, если он существует
        previous_task_id = redis_client.get(f"active_parser_{parser_name}")
        if previous_task_id:
            previous_task_id = previous_task_id.decode()
            if previous_task_id != self.request.id and not kwargs.get(
                    'is_first_run', False):
                logger.info(
                    f"Найдена предыдущая задача {previous_task_id} "
                    f"для парсера {parser_name}, планируется остановка.")
                # Запускаем таск для остановки предыдущего инстанса через минуту
                schedule_stop_previous_instance.apply_async(
                    (parser_name, previous_task_id), countdown=60)
            else:
                logger.info(
                    f"Первый запуск или совпадение идентификаторов, "
                    f"остановка предыдущей задачи {previous_task_id} "
                    f"для парсера {parser_name} не требуется.")
        else:
            logger.info(
                f"Предыдущая задача для парсера {parser_name} не найдена.")

        # Удаление is_first_run из kwargs перед созданием парсера
        kwargs.pop('is_first_run', None)

        # Сохраняем текущий task_id в Redis сразу
        redis_client.set(f"active_parser_{parser_name}", self.request.id)
        logger.info(
            f"Установлена активная задача {self.request.id} "
            f"для парсера {parser_name} в Redis.")

        # Создаем новый инстанс парсера и запускаем его
        parser = parser_class(*args, **kwargs)
        asyncio.run(parser.run())
        logger.info(
            f"Парсер {parser_name} с task_id {self.request.id} успешно завершен.")

    except urllib3.exceptions.ProtocolError as e:
        logger.error(
            f"Ошибка протокола при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
    except Exception as e:
        logger.error(f"Ошибка при выполнении парсера {parser_name}: {e}")
        self.retry(exc=e)
    finally:
        if parser:
            asyncio.run(parser.close())
        # Удаление метаданных задачи
        clear_task_metadata(self.request.id)


@celery_app.task
def check_and_start_parsers(is_first_run: bool = False):
    """
    Проверяет активные задачи парсеров и запускает их, если они не работают.
    """
    logger.info("Запуск проверки активных задач парсеров.")

    if is_first_run:
        logger.info("Первый запуск, удаление всех celery-task-meta ключей из Redis.")
        delete_celery_task_meta_keys()

    inspect = current_app.control.inspect()
    active_tasks = inspect.active()  # Получаем активные задачи

    # Инициализация Redis-клиента
    redis_client = RedisClient()

    # Проверка и инициализация словаря translate_cash
    asyncio.run(check_and_init_translate_cash(redis_client))

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
                    f"Старая задача {task['id']} для парсера"
                    f" {parser_name} была остановлена.")

        active_task_id = redis_client.get(f"active_parser_{parser_name}")
        if not active_task_id or is_first_run:
            logger.info(
                f"Активная задача для парсера {parser_name} не найдена, "
                f"запуск новой задачи через 30 секунд.")
            time.sleep(30)
            parse_some_data.apply_async(args=(parser_name,),
                                        kwargs={'is_first_run': is_first_run})
        else:
            logger.info(
                f"Активная задача {active_task_id.decode()} для парсера "
                f"{parser_name} найдена, запуск новой задачи не требуется.")