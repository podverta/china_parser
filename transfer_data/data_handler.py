import json
from typing import Optional
from fastapi import FastAPI
from aioredis import Redis
from transfer_data.socketio_server import sio
from app.main import app

async def send_and_save_data(data: str, service_name: str) -> None:
    """
    Sends data to the Socket.IO server and saves it in Redis.

    :param data: Data to send and save.
    :param service_name: The name of the service from which the data originated.
    :param app: The FastAPI application instance.
    """
    try:
        # Access initialized clients
        redis: Redis = app.state.redis

        # Convert data to JSON
        json_data = json.dumps(data, ensure_ascii=False)

        # Send data to the Socket.IO server
        await sio.emit('message', json_data)

        # Save data in Redis
        await redis.set(service_name, json_data)

        print("Data sent to Socket.IO and saved to Redis.")

    except Exception as e:
        print(f'Error sending data: {str(e)}')

async def set_load_data_redis(
        action: str,
        key: str,
        data: Optional[dict] = None
) -> Optional[dict]:
    """
    Saves or loads data from Redis depending on the action.

    :param action: Action - 'save' to save, 'load' to load.
    :param key: Key for the data.
    :param app: The FastAPI application instance.
    :param data: Data to save (only for 'save' action).
    :return: Loaded data (if action is 'load'), otherwise None.
    """
    try:
        # Access the initialized Redis client
        redis: Redis = app.state.redis

        if action == "save":
            if data is None:
                raise ValueError("Data must be provided for 'save' action")

            # Convert data to JSON
            json_data = json.dumps(data, ensure_ascii=False)
            await redis.set(key, json_data)
            print(f"Data saved to Redis with key: {key}")

        elif action == "load":
            # Load data from Redis
            json_data = await redis.get(key)
            if json_data is None:
                print(f"No data found for key: {key}")
                return None

            # Convert data from JSON
            data = json.loads(json_data.decode('utf-8'))
            print(f"Data loaded from Redis with key: {key}")
            return data

        else:
            raise ValueError("Action must be either 'load' or 'save'")

    except Exception as e:
        print(f"Error handling Redis data: {str(e)}")
        return None
