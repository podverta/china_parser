import os
import aioredis
from aioredis import Redis
from dotenv import load_dotenv

load_dotenv()
REDIS_URL = os.getenv('REDIS_URL')


class RedisClient:
    def __init__(self, ):
        self.url = REDIS_URL
        self.redis: Redis | None = None

    async def connect(self) -> None:
        """
        Устанавливает соединение с Redis.
        """
        try:
            self.redis = await aioredis.from_url(self.url)
            print(f"Connected to Redis at {self.url}")
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Закрывает соединение с Redis.
        """
        if self.redis:
            await self.redis.close()
            print("Disconnected from Redis")
