import asyncio
from collections import defaultdict


class EventBroker:
    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, job_id: str, payload: dict) -> None:
        queues = list(self._queues.get(job_id, []))
        for queue in queues:
            await queue.put(payload)

    async def subscribe(self, job_id: str):
        queue = asyncio.Queue()
        self._queues[job_id].append(queue)
        try:
            while True:
                payload = await queue.get()
                yield payload
        finally:
            self._queues[job_id].remove(queue)


event_broker = EventBroker()
