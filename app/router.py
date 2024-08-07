import aiofiles
import json
from typing import Any, List
from fastapi import APIRouter, HTTPException
from services_app.tasks import parse_some_data
from app.schema import ParserRequest
from transfer_data.redis_client import RedisClient

route = APIRouter()
# Удаляем loop = asyncio.get_event_loop() так как оно не используется

@route.post("/run_parser/")
async def run_parser(request: ParserRequest):
    """
    Эндпоинт для запуска парсера.

    :param request: Данные для запуска парсера (имя класса парсера, аргументы и именованные аргументы)
    :return: Сообщение о статусе запуска парсера
    """
    parsers_name = [
        'FetchAkty',
        'FB'
    ]
    try:
        if request.parser_name not in parsers_name:
            raise HTTPException(status_code=400, detail="Parser class not found")

        # Запускаем задачу Celery
        parse_some_data.delay(request.parser_name, *request.args, **request.kwargs)

        return {"status": "Parser is running", "parser": request.parser_name}
    except HTTPException as e:
        # HTTPException уже правильно формируется выше, можно просто прокинуть дальше
        raise e
    except Exception as e:
        # Важно отлавливать все возможные ошибки и возвращать понятный ответ
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@route.get("/logs/akty")
async def get_akty_logs():
    """
    Эндпоинт для получения последних 50 строк из файла логов akty_debug.log.

    :return: Содержимое последних 50 строк лог-файла
    """
    log_file_path = 'logs/akty_debug.log'
    try:
        async with aiofiles.open(log_file_path, 'r') as log_file:
            lines = await log_file.readlines()
            # Получаем последние 50 строк
            last_lines = lines[-50:]
            return {"logs": last_lines}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log file not found")
    except Exception as e:
        # Детализированный ответ об ошибке
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")


@route.get("/logs/fb")
async def get_fb_logs():
    """
    Эндпоинт для получения последних 50 строк из файла логов fb_debug.log.

    :return: Содержимое последних 50 строк лог-файла
    """
    log_file_path = 'logs/fb_debug.log'
    try:
        async with aiofiles.open(log_file_path, 'r') as log_file:
            lines = await log_file.readlines()
            # Получаем последние 50 строк
            last_lines = lines[-50:]
            return {"logs": last_lines}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

@route.get("/get-game/{site}/{league}/{opponent_0}/{opponent_1}")
async def get_game(
        site: str,
        league: str,
        opponent_0: str,
        opponent_1: str
) -> dict:
    """
     Получает данные игры по составному ключу.

     Args:
         site (str): Сайт, откуда пришли данные.
         league (str): Название лиги.
         opponent_0 (str): Имя первой команды.
         opponent_1 (str): Имя второй команды.

     Returns:
         dict: Данные игры или сообщение об ошибке, если игра не найдена.
     """
    try:
        redis_client = RedisClient()
        await redis_client.connect()

        # Формируем ключ в нижнем регистре
        key = (f"{site.lower()}, {league.lower()}, "
               f"{opponent_0.lower()}, {opponent_1.lower()}")

        # Получаем данные из Redis
        data = await redis_client.get_last_items(key)

        if not data:
            raise HTTPException(status_code=404, detail=f"Игра {key} не найдена {key}, {opponent_1}")

        return {"games": data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))