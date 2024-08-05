# redis_handler.py
import json
from typing import Optional
from app.main import app

async def send_and_save_data(data: str, service_name: str) -> None:
    """
    Отправляет данные на Socket.IO сервер и сохраняет их в Redis.

    :param data: Данные для отправки и сохранения.
    :param service_name: Наименование сервиса откуда пришли данные
    """
    try:
        # Получаем доступ к инициализированным клиентам
        redis = app.state.redis
        sio = app.state.sio

        # Преобразование данных в JSON
        json_data = json.dumps(data, ensure_ascii=False)

        # Отправка данных на сервер Socket.IO
        await sio.emit('message', json_data)

        # Сохранение данных в Redis
        await redis.set(service_name, json_data)

        print("Data sent to Socket.IO and saved to Redis.")

    except Exception as e:
        print(f'Error sending data: {str(e)}')

async def set_load_data_redis(action: str, key: str, data: Optional[dict] = None) -> Optional[dict]:
    """
    Сохраняет или загружает данные из Redis в зависимости от действия.

    :param action: Действие - 'save' для сохранения, 'load' для загрузки.
    :param key: Ключ для данных.
    :param data: Данные для сохранения (только для действия 'save').
    :return: Загруженные данные (если действие 'load'), иначе None.
    """
    try:
        # Получаем доступ к инициализированному клиенту Redis
        redis = app.state.redis

        if action == "save":
            if data is None:
                raise ValueError("Data must be provided for 'save' action")

            # Преобразование данных в JSON
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
