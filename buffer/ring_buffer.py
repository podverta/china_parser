from collections import deque
from typing import Any, Dict, List

class AsyncLeagueRingBuffer:
    def __init__(self, size: int):
        self.size = size
        self.buffers: Dict[str, deque] = {}

    async def append(self, league: str, item: Any):
        if league not in self.buffers:
            self.buffers[league] = deque(maxlen=self.size)
        self.buffers[league].append(item)

    async def get_all(self, league: str) -> List[Any]:
        return list(self.buffers.get(league, []))
