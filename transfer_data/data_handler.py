import json
from app.main import app


async def send_and_save_data(
        data: str,
        service_name: str
) -> None:
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

async def set_load_data_resid(
        data: str,
        service_name: str
) -> None:
    """
    Отправляет данные на Socket.IO сервер и сохраняет их в Redis.

    :param data: Данные для отправки и сохранения.
    :param service_name: Наименование сервиса откуда пришли данные
    """
    try:
        # Получаем доступ к инициализированным клиентам
        redis = app.state.redis

        # Преобразование данных в JSON
        json_data = json.dumps(data, ensure_ascii=False)

        # Отправка данных на сервер Socket.IO
        await sio.emit('message', json_data)

        # Сохранение данных в Redis
        await redis.set(service_name, json_data)

        print("Data sent to Socket.IO and saved to Redis.")

    except Exception as e:
        print(f'Error sending data: {str(e)}')
