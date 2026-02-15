import asyncio
import logging

logger = logging.getLogger(__name__)


class CaseEventBus:
    """Simple pub/sub for broadcasting case updates to hospital dashboard clients."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._global_subscribers: set[asyncio.Queue] = set()

    def subscribe_all(self) -> asyncio.Queue:
        """Subscribe to all case events. Returns a queue to await events from."""
        queue: asyncio.Queue = asyncio.Queue()
        self._global_subscribers.add(queue)
        return queue

    def unsubscribe_all(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from all case events."""
        self._global_subscribers.discard(queue)

    def subscribe(self, case_id: str) -> asyncio.Queue:
        """Subscribe to events for a specific case."""
        queue: asyncio.Queue = asyncio.Queue()
        if case_id not in self._subscribers:
            self._subscribers[case_id] = set()
        self._subscribers[case_id].add(queue)
        return queue

    def unsubscribe(self, case_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from a specific case's events."""
        if case_id in self._subscribers:
            self._subscribers[case_id].discard(queue)
            if not self._subscribers[case_id]:
                del self._subscribers[case_id]

    async def publish(self, case_id: str, event: dict) -> None:
        """Publish an event for a case to all subscribers."""
        event["case_id"] = case_id

        # Notify case-specific subscribers
        for queue in self._subscribers.get(case_id, set()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full for case %s subscriber", case_id)

        # Notify global subscribers
        for queue in self._global_subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Global event queue full")


# Singleton instance
event_bus = CaseEventBus()
