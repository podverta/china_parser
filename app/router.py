import asyncio
from fastapi import APIRouter, HTTPException, Request
from services_app.tasks import parse_some_data
from app.schema import ParserRequest
from typing import Any, List
from config import  log_buffer
route = APIRouter()
loop = asyncio.get_event_loop()

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
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@route.get("/logs/akty")
async def get_akty_logs():
    """
    Эндпоинт для получения последних 50 строк из файла логов akty_debug.log.

    :return: Содержимое последних 50 строк лог-файла
    """
    log_file_path = 'logs/akty_debug.log'
    try:
        with open(log_file_path, 'r') as log_file:
            lines = log_file.readlines()
            # Получаем последние 50 строк
            last_lines = lines[-50:]
            return {"logs": last_lines}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@route.get("/logs/fb")
async def get_akty_logs():
    """
    Эндпоинт для получения последних 50 строк из файла логов akty_debug.log.

    :return: Содержимое последних 50 строк лог-файла
    """
    log_file_path = 'logs/fb_debug.log'
    try:
        with open(log_file_path, 'r') as log_file:
            lines = log_file.readlines()
            # Получаем последние 50 строк
            last_lines = lines[-50:]
            return {"logs": last_lines}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_logs_from_redis(redis, league: str) -> List[Any]:
    logs = await redis.lrange(f"logs:{league}", 0, 299)
    return [log.decode("utf-8") for log in logs]


@route.get("/logs/{league}")
async def get_logs(league: str, request: Request):
    redis = request.app.state.redis
    redis_logs = await get_logs_from_redis(redis, league)
    buffer_logs = await log_buffer.get_all(league)
    return {"redis_logs": redis_logs, "buffer_logs": buffer_logs}