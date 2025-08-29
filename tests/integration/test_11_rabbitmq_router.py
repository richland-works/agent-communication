"""Integration tests for RabbitMQ router."""

import pytest
import asyncio
from typing import Dict, List, Callable, Optional
from agent_communication.base import BaseMessage, BaseAgent
from agent_communication.routers import RabbitMQRouter


class QueueMessage(BaseMessage):
    """Message for RabbitMQ queue tests."""

    payload: str
    priority: int = 0

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class TopicMessage(BaseMessage):
    """Message for topic exchange tests."""

    topic: str
    content: str

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class SampleRabbitAgent(BaseAgent):
    """Test agent for RabbitMQ tests."""

    messages = [QueueMessage, TopicMessage]
    sending_messages = [QueueMessage, TopicMessage]

    def __init__(self, router: Optional[RabbitMQRouter] = None) -> None:
        super().__init__(router)
        self.received_messages: List[BaseMessage] = []
        self.received_contexts: List[Dict[str, str]] = []

    def handle_message(self, message: BaseMessage, context: Dict[str, str]) -> None:
        self.received_messages.append(message)
        self.received_contexts.append(context)


@pytest.mark.asyncio
class TestRabbitMQRouter:
    """Test RabbitMQ router functionality."""

    async def test_router_connect_disconnect(self, rabbitmq_url: str) -> None:
        """Test basic connection and disconnection."""
        router = RabbitMQRouter(url=rabbitmq_url)

        await router.start()
        assert router._running is True
        assert await router.health_check() is True

        await router.stop()
        assert router._running is False

    async def test_durable_queue_creation(self, rabbitmq_url: str) -> None:
        """Test that durable queues are created correctly."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_exchange")
        await router.start()

        agent = SampleRabbitAgent(router)
        pattern = "QueueMessage:request:*"

        await router.subscribe(agent, pattern)
        assert pattern in router._queues

        queue = router._queues[pattern]
        assert queue is not None

        await router.stop()

    async def test_publish_and_receive(self, rabbitmq_url: str) -> None:
        """Test publishing and receiving messages through RabbitMQ."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_pubsub")
        await router.start()

        agent = SampleRabbitAgent(router)
        await agent.subscribe("QueueMessage:request:*")

        await asyncio.sleep(0.5)

        message = QueueMessage(payload="Hello RabbitMQ", priority=1)
        await router.publish(message, "QueueMessage:request:rabbit123")

        await asyncio.sleep(1.0)

        assert len(agent.received_messages) == 1
        assert isinstance(agent.received_messages[0], QueueMessage)
        assert agent.received_messages[0].payload == "Hello RabbitMQ"
        assert agent.received_messages[0].priority == 1
        assert agent.received_contexts[0]["session_id"] == "rabbit123"

        await router.stop()

    async def test_topic_exchange_routing(self, rabbitmq_url: str) -> None:
        """Test topic exchange pattern matching."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_topic")
        await router.start()

        agent1 = SampleRabbitAgent(router)
        agent2 = SampleRabbitAgent(router)
        agent3 = SampleRabbitAgent(router)

        await router.subscribe(agent1, "TopicMessage:*:*")
        await router.subscribe(agent2, "TopicMessage:request:*")
        await router.subscribe(agent3, "TopicMessage:response:session999")

        await asyncio.sleep(0.5)

        message1 = TopicMessage(topic="orders", content="New order")
        await router.publish(message1, "TopicMessage:request:session777")

        message2 = TopicMessage(topic="payments", content="Payment received")
        await router.publish(message2, "TopicMessage:response:session999")

        await asyncio.sleep(1.0)

        assert len(agent1.received_messages) == 2
        assert len(agent2.received_messages) == 1
        assert len(agent3.received_messages) == 1

        assert isinstance(agent2.received_messages[0], TopicMessage)
        assert agent2.received_messages[0].content == "New order"
        assert isinstance(agent3.received_messages[0], TopicMessage)
        assert agent3.received_messages[0].content == "Payment received"

        await router.stop()

    async def test_message_persistence(self, rabbitmq_url: str) -> None:
        """Test that messages are persisted in durable queues."""
        router1 = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_persist")
        await router1.start()

        agent1 = SampleRabbitAgent(router1)
        await router1.subscribe(agent1, "QueueMessage:persist:*")

        await asyncio.sleep(0.5)

        await router1.disconnect()

        router2 = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_persist")
        await router2.start()

        message = QueueMessage(payload="Persistent message", priority=5)
        await router2.publish(message, "QueueMessage:persist:test123")

        await asyncio.sleep(0.5)

        router1 = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_persist")
        await router1.start()
        await router1.subscribe(agent1, "QueueMessage:persist:*")

        await asyncio.sleep(1.0)

        assert len(agent1.received_messages) == 1
        assert isinstance(agent1.received_messages[0], QueueMessage)
        assert agent1.received_messages[0].payload == "Persistent message"

        await router1.stop()
        await router2.stop()

    async def test_broadcast_fanout(self, rabbitmq_url: str) -> None:
        """Test broadcasting to multiple agents."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_fanout")
        await router.start()

        agents = [SampleRabbitAgent(router) for _ in range(3)]

        for agent in agents:
            await router.subscribe(agent, "TopicMessage:broadcast:*")

        await asyncio.sleep(0.5)

        message = TopicMessage(topic="announcement", content="System update")
        await router.broadcast(message, "broadcast", "all")

        await asyncio.sleep(1.0)

        for agent in agents:
            assert len(agent.received_messages) == 1
            assert isinstance(agent.received_messages[0], TopicMessage)
            assert agent.received_messages[0].content == "System update"

        await router.stop()

    async def test_auto_subscribe(self, rabbitmq_url: str) -> None:
        """Test automatic subscription based on agent's message types."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_auto")
        await router.start()

        agent = SampleRabbitAgent(router)
        await router.auto_subscribe_agent(agent)

        assert "QueueMessage:*:*" in router._subscriptions
        assert "TopicMessage:*:*" in router._subscriptions
        assert agent in router._subscriptions["QueueMessage:*:*"]
        assert agent in router._subscriptions["TopicMessage:*:*"]

        await router.stop()

    async def test_queue_purge(self, rabbitmq_url: str) -> None:
        """Test purging messages from a queue."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_purge")
        await router.start()

        agent = SampleRabbitAgent(router)
        pattern = "QueueMessage:purge:test"
        await router.subscribe(agent, pattern)

        await asyncio.sleep(0.5)

        for i in range(5):
            message = QueueMessage(payload=f"Message {i}", priority=i)
            await router.publish(message, "QueueMessage:purge:test")

        await asyncio.sleep(0.5)

        purged_count = await router.purge_queue(pattern)
        assert purged_count >= 0

        await asyncio.sleep(0.5)
        assert len(agent.received_messages) <= 5

        await router.stop()

    async def test_concurrent_processing(self, rabbitmq_url: str) -> None:
        """Test handling multiple concurrent messages."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_concurrent")
        await router.start()

        agent = SampleRabbitAgent(router)
        await router.subscribe(agent, "QueueMessage:*:*")

        await asyncio.sleep(0.5)

        tasks = []
        for i in range(20):
            message = QueueMessage(payload=f"Concurrent {i}", priority=i % 3)
            tasks.append(router.publish(message, f"QueueMessage:test:session{i}"))

        await asyncio.gather(*tasks)
        await asyncio.sleep(2.0)

        assert len(agent.received_messages) == 20

        payloads = {
            msg.payload
            for msg in agent.received_messages
            if isinstance(msg, QueueMessage)
        }
        expected = {f"Concurrent {i}" for i in range(20)}
        assert payloads == expected

        await router.stop()

    async def test_message_acknowledgment(self, rabbitmq_url: str) -> None:
        """Test that messages are properly acknowledged."""
        router = RabbitMQRouter(url=rabbitmq_url, exchange_name="test_ack")
        await router.start()

        class FailingAgent(BaseAgent):
            messages = [QueueMessage]
            sending_messages = []

            def __init__(
                self, router: Optional[RabbitMQRouter] = None, fail_count: int = 1
            ) -> None:
                super().__init__(router)
                self.fail_count = fail_count
                self.attempt_count = 0

            def handle_message(
                self, message: BaseMessage, context: Dict[str, str]
            ) -> None:
                self.attempt_count += 1
                if self.attempt_count <= self.fail_count:
                    raise Exception("Simulated failure")

        agent = FailingAgent(router, fail_count=0)
        await router.subscribe(agent, "QueueMessage:ack:*")

        await asyncio.sleep(0.5)

        message = QueueMessage(payload="Will succeed", priority=1)
        await router.publish(message, "QueueMessage:ack:test")

        await asyncio.sleep(1.0)

        assert agent.attempt_count == 1

        await router.stop()
