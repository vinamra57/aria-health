"""Tests for the CaseEventBus pub/sub system."""

import asyncio

from app.services.event_bus import CaseEventBus


class TestCaseEventBus:
    async def test_global_subscribe_receives_events(self):
        bus = CaseEventBus()
        queue = bus.subscribe_all()

        await bus.publish("case-1", {"type": "test", "data": "hello"})

        event = queue.get_nowait()
        assert event["case_id"] == "case-1"
        assert event["type"] == "test"
        assert event["data"] == "hello"

    async def test_case_specific_subscribe(self):
        bus = CaseEventBus()
        q1 = bus.subscribe("case-1")
        q2 = bus.subscribe("case-2")

        await bus.publish("case-1", {"type": "update"})

        event = q1.get_nowait()
        assert event["case_id"] == "case-1"
        assert q2.empty()

    async def test_unsubscribe_all(self):
        bus = CaseEventBus()
        queue = bus.subscribe_all()
        bus.unsubscribe_all(queue)

        await bus.publish("case-1", {"type": "test"})
        assert queue.empty()

    async def test_unsubscribe_case(self):
        bus = CaseEventBus()
        queue = bus.subscribe("case-1")
        bus.unsubscribe("case-1", queue)

        await bus.publish("case-1", {"type": "test"})
        assert queue.empty()

    async def test_multiple_global_subscribers(self):
        bus = CaseEventBus()
        q1 = bus.subscribe_all()
        q2 = bus.subscribe_all()

        await bus.publish("case-1", {"type": "test"})

        assert not q1.empty()
        assert not q2.empty()
        assert q1.get_nowait()["type"] == "test"
        assert q2.get_nowait()["type"] == "test"

    async def test_both_global_and_case_subscribers(self):
        bus = CaseEventBus()
        global_q = bus.subscribe_all()
        case_q = bus.subscribe("case-1")

        await bus.publish("case-1", {"type": "test"})

        assert not global_q.empty()
        assert not case_q.empty()

    async def test_unsubscribe_nonexistent_case(self):
        bus = CaseEventBus()
        queue: asyncio.Queue = asyncio.Queue()
        # Should not raise
        bus.unsubscribe("nonexistent", queue)

    async def test_unsubscribe_cleans_up_empty_set(self):
        bus = CaseEventBus()
        queue = bus.subscribe("case-1")
        bus.unsubscribe("case-1", queue)
        assert "case-1" not in bus._subscribers

    async def test_publish_adds_case_id(self):
        bus = CaseEventBus()
        queue = bus.subscribe_all()
        await bus.publish("my-case", {"type": "hello"})
        event = queue.get_nowait()
        assert event["case_id"] == "my-case"
