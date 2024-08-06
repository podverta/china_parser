import os
import aioredis
from dotenv import load_dotenv
from typing import Any, Optional

load_dotenv()

REDIS_URL = os.getenv('REDIS_URL')


class RedisClient:
    """
    Класс для асинхронной работы с Redis.

    Attributes:
        redis_url (str): URL подключения к Redis.
        pool (aioredis.ConnectionPool): Пул подключений к Redis.

    Methods:
        __init__(redis_url: str): Инициализирует класс с заданным URL Redis.
        connect(): Устанавливает соединение с Redis.
        close(): Закрывает соединение с Redis.
        set_data(key: str, value: Any): Сохраняет данные в Redis по ключу.
        get_data(key: str) -> Optional[Any]: Загружает данные из Redis по ключу.
    """

    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self.pool: Optional[aioredis.ConnectionPool] = None

    async def connect(self):
        """Устанавливает соединение с Redis."""
        self.pool = aioredis.ConnectionPool.from_url(self.redis_url)

    async def close(self):
        """Закрывает соединение с Redis."""
        if self.pool:
            await self.pool.disconnect()

    async def set_data(self, key: str, value: Any):
        """
        Сохраняет данные в Redis по ключу.

        Args:
            key (str): Ключ для сохранения данных.
            value (Any): Данные для сохранения.
        """
        if self.pool:
            async with aioredis.Redis(connection_pool=self.pool) as redis:
                await redis.set(key, value)

    async def get_data(self, key: str) -> Optional[Any]:
        """
        Загружает данные из Redis по ключу.

        Args:
            key (str): Ключ для загрузки данных.

        Returns:
            Optional[Any]: Загруженные данные или None, если ключ не найден.
        """
        if self.pool:
            async with aioredis.Redis(connection_pool=self.pool) as redis:
                return await redis.get(key)