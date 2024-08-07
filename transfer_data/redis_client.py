import os
import json
import aioredis
from typing import Any, Optional, List
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
        add_to_list(key: str, value: Any, max_len: int): Добавляет данные в список Redis.
        get_last_items(key: str, count: int) -> List[Any]: Получает последние элементы из списка Redis.
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
                data = await redis.get(key)
                if data:
                    return data.decode("utf-8")
                return None

    async def add_to_list(self, key: str, value: Any, max_len: int = 300):
        """
        Добавляет данные в список Redis. Если размер списка превышает max_len, удаляет старые элементы.

        Args:
            key (str): Ключ для сохранения данных.
            value (Any): Данные для сохранения.
            max_len (int): Максимальное количество элементов в списке. По умолчанию 300.
        """
        if self.pool:
            async with aioredis.Redis(connection_pool=self.pool) as redis:
                # Добавляем элемент в конец списка
                await redis.lpush(key, value)
                # Обрезаем список до max_len элементов
                await redis.ltrim(key, -max_len, -1)

    async def get_last_items(self, key: str, count: int = 300) -> List[Any]:
        """
        Получает последние элементы из списка Redis.

        Args:
            key (str): Ключ для загрузки данных.
            count (int): Количество элементов для загрузки. По умолчанию 300.

        Returns:
            List[Any]: Список последних элементов.
        """
        if self.pool:
            async with aioredis.Redis(connection_pool=self.pool) as redis:
                items = await redis.lrange(key, 0, count - 1)
                # Декодируем байты и преобразуем в JSON объекты
                return [json.loads(item.decode("utf-8")) for item in items]
