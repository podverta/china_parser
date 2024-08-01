import aioredis
from buffer.ring_buffer import AsyncLeagueRingBuffer
import logging

async def create_redis_pool():
    return await aioredis.create_redis_pool("redis://localhost")

class AsyncBufferHandler(logging.Handler):
    def __init__(self, ring_buffer: AsyncLeagueRingBuffer, redis):
        super().__init__()
        self.ring_buffer = ring_buffer
        self.redis = redis

    async def emit(self, league: str, record):
        log_entry = self.format(record)
        await self.ring_buffer.append(league, log_entry)
        await self.redis.lpush(f"logs:{league}", log_entry)
        await self.redis.ltrim(f"logs:{league}", 0, 299)

log_buffer = AsyncLeagueRingBuffer(300)
logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)
