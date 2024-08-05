import json
from typing import Any, Optional
from aioredis import Redis
from app.main import app

async def handle_redis_data(action: str, key: str, data: Optional[Any] = None) -> Optional[Any]:
    """
    Управляет данными в Redis. Поддерживает действия "load" и "save".

    :param action: Действие ("load" или "save").
    :param key: Ключ для сохранения или загрузки данных.
    :param data: Данные для сохранения (необязательно при загрузке).
    :return: Загруженные данные (если действие "load"), иначе None.
    """
    try:
        # Получаем доступ к инициализированному клиенту Redis
        redis: Redis = app.state.redis

        if action == "save":
            if data is None:
                raise ValueError("Data must be provided for 'save' action")

            # Преобразование данных в JSON для сохранения
            json_data = json.dumps(data, ensure_ascii=False)
            await redis.set(key, json_data)
            print(f"Data saved to Redis with key: {key}")

        elif action == "load":
            # Загрузка данных из Redis
            json_data = await redis.get(key)
            if json_data is None:
                print(f"No data found for key: {key}")
                return None

            # Преобразование данных из JSON
            data = json.loads(json_data.decode('utf-8'))
            print(f"Data loaded from Redis with key: {key}")
            return data

        else:
            raise ValueError("Action must be either 'load' or 'save'")

    except Exception as e:
        print(f"Error handling Redis data: {str(e)}")
        return None