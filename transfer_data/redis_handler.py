import json
from typing import Any, Optional
from fastapi import FastAPI
from aioredis import Redis


async def handle_redis_data(action: str, key: str, app: FastAPI,
                            data: Optional[Any] = None) -> Optional[Any]:
    """
    Handles saving or loading data from Redis based on the action.

    :param action: Action ('load' or 'save').
    :param key: Key for saving or loading data.
    :param app: FastAPI app instance for accessing state.
    :param data: Data to save (if action is 'save').
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

