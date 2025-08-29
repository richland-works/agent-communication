"""Integration tests for Redis router."""

import pytest
import asyncio
from typing import Dict, List, Callable, Optional
from agent_communication.base import BaseMessage, BaseAgent
from agent_communication.routers import RedisRouter


class SampleMessage(BaseMessage):
    """Sample message for router tests."""

    content: str

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class BroadcastMessage(BaseMessage):
    """Message for broadcast tests."""

    data: str

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class SampleAgent(BaseAgent):
    """Test agent for router tests."""

    messages = [SampleMessage, BroadcastMessage]
    sending_messages = [SampleMessage, BroadcastMessage]

    def __init__(self, router: Optional[RedisRouter] = None) -> None:
        super().__init__(router)
        self.received_messages: List[BaseMessage] = []
        self.received_contexts: List[Dict[str, str]] = []

    def handle_message(self, message: BaseMessage, context: Dict[str, str]) -> None:
        self.received_messages.append(message)
        self.received_contexts.append(context)


@pytest.mark.asyncio
class TestRedisRouter:
    """Test Redis router functionality."""

    async def test_router_connect_disconnect(self, redis_url: str) -> None:
        """Test basic connection and disconnection."""
        router = RedisRouter(url=redis_url)

        await router.start()
        assert router._running is True
        assert await router.health_check() is True

        await router.stop()
        assert router._running is False

    async def test_subscribe_unsubscribe(self, redis_url: str) -> None:
        """Test agent subscription and unsubscription."""
        router = RedisRouter(url=redis_url)
        await router.start()

        agent = SampleAgent(router)
        pattern = "SampleMessage:*:*"

        await router.subscribe(agent, pattern)
        assert pattern in router._subscriptions
        assert agent in router._subscriptions[pattern]

        await router.unsubscribe(agent, pattern)
        assert pattern not in router._subscriptions

        await router.stop()

    async def test_publish_and_receive(self, redis_url: str) -> None:
        """Test publishing and receiving messages."""
        router = RedisRouter(url=redis_url)
        await router.start()

        agent = SampleAgent(router)
        await agent.subscribe("SampleMessage:request:*")

        await asyncio.sleep(0.1)

        message = SampleMessage(content="Hello Redis")
        await router.publish(message, "SampleMessage:request:session123")

        await asyncio.sleep(0.2)

        assert len(agent.received_messages) == 1
        assert isinstance(agent.received_messages[0], SampleMessage)
        assert agent.received_messages[0].content == "Hello Redis"
        assert agent.received_contexts[0]["session_id"] == "session123"
        assert agent.received_contexts[0]["direction"] == "request"

        await router.stop()

    async def test_broadcast_to_multiple_agents(self, redis_url: str) -> None:
        """Test broadcasting to multiple subscribed agents."""
        router = RedisRouter(url=redis_url)
        await router.start()

        agent1 = SampleAgent(router)
        agent2 = SampleAgent(router)
        agent3 = SampleAgent(router)

        await router.subscribe(agent1, "BroadcastMessage:*:*")
        await router.subscribe(agent2, "BroadcastMessage:*:*")
        await router.subscribe(agent3, "BroadcastMessage:response:*")

        await asyncio.sleep(0.1)

        message = BroadcastMessage(data="Broadcast data")
        await router.broadcast(message, "response", "broadcast123")

        await asyncio.sleep(0.2)

        assert len(agent1.received_messages) == 1
        assert len(agent2.received_messages) == 1
        assert len(agent3.received_messages) == 1
        for agent in [agent1, agent2, agent3]:
            assert isinstance(agent.received_messages[0], BroadcastMessage)
        assert all(
            msg.data == "Broadcast data"
            for agent in [agent1, agent2, agent3]
            for msg in agent.received_messages
            if isinstance(msg, BroadcastMessage)
        )

        await router.stop()

    async def test_pattern_matching(self, redis_url: str) -> None:
        """Test pattern matching for subscriptions."""
        router = RedisRouter(url=redis_url)
        await router.start()

        specific_agent = SampleAgent(router)
        wildcard_agent = SampleAgent(router)

        await router.subscribe(specific_agent, "SampleMessage:request:session456")
        await router.subscribe(wildcard_agent, "SampleMessage:*:*")

        await asyncio.sleep(0.1)

        message = SampleMessage(content="Pattern test")
        await router.publish(message, "SampleMessage:request:session456")

        await asyncio.sleep(0.2)

        assert len(specific_agent.received_messages) == 1
        assert len(wildcard_agent.received_messages) == 1

        await router.publish(message, "SampleMessage:response:session789")

        await asyncio.sleep(0.2)

        assert len(specific_agent.received_messages) == 1
        assert len(wildcard_agent.received_messages) == 2

        await router.stop()

    async def test_auto_subscribe(self, redis_url: str) -> None:
        """Test automatic subscription based on agent's message types."""
        router = RedisRouter(url=redis_url)
        await router.start()

        agent = SampleAgent(router)
        await router.auto_subscribe_agent(agent)

        assert "SampleMessage:*:*" in router._subscriptions
        assert "BroadcastMessage:*:*" in router._subscriptions
        assert agent in router._subscriptions["SampleMessage:*:*"]
        assert agent in router._subscriptions["BroadcastMessage:*:*"]

        await router.stop()

    async def test_agent_publish_validation(self, redis_url: str) -> None:
        """Test that agents can only send allowed message types."""
        router = RedisRouter(url=redis_url)
        await router.start()

        class RestrictedAgent(BaseAgent):
            messages = [SampleMessage]
            sending_messages = []

            def __init__(self, router: Optional[RedisRouter] = None) -> None:
                super().__init__(router)

            def handle_message(
                self, message: BaseMessage, context: Dict[str, str]
            ) -> None:
                pass

        agent = RestrictedAgent(router)
        message = SampleMessage(content="Not allowed")

        with pytest.raises(ValueError, match="not allowed to send"):
            await agent.publish(message, "SampleMessage:request:test")

        await router.stop()

    async def test_concurrent_messages(self, redis_url: str) -> None:
        """Test handling multiple concurrent messages."""
        router = RedisRouter(url=redis_url)
        await router.start()

        agent = SampleAgent(router)
        await router.subscribe(agent, "SampleMessage:*:*")

        await asyncio.sleep(0.1)

        tasks = []
        for i in range(10):
            message = SampleMessage(content=f"Message {i}")
            tasks.append(router.publish(message, f"SampleMessage:request:session{i}"))

        await asyncio.gather(*tasks)
        await asyncio.sleep(0.5)

        assert len(agent.received_messages) == 10

        contents = {
            msg.content
            for msg in agent.received_messages
            if isinstance(msg, SampleMessage)
        }
        expected = {f"Message {i}" for i in range(10)}
        assert contents == expected

        await router.stop()
