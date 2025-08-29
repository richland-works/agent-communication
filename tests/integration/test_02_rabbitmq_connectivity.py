"""Test RabbitMQ container connectivity and basic operations."""

import pytest
import asyncio
import aio_pika
from aio_pika import Message, ExchangeType
from typing import Dict


@pytest.mark.asyncio
async def test_rabbitmq_connection(rabbitmq_url: str) -> None:
    """Test that we can connect to RabbitMQ container."""
    print(f"\nTesting RabbitMQ connection at: {rabbitmq_url}")

    connection = None
    try:
        # Connect to RabbitMQ
        connection = await aio_pika.connect_robust(rabbitmq_url)
        assert connection is not None, "Failed to create connection"
        assert not connection.is_closed, "Connection should be open"

        # Create a channel
        channel = await connection.channel()
        assert channel is not None, "Failed to create channel"
        assert not channel.is_closed, "Channel should be open"

        print("✓ RabbitMQ connection successful")

        # Get some server properties (if available)
        # Note: We use getattr() instead of direct attribute access because:
        # - AbstractRobustConnection doesn't expose 'connection' in its type definition
        # - The actual runtime implementation may have this attribute
        # - Using getattr() satisfies both Pylance and mypy without type: ignore comments
        if hasattr(connection, "connection"):
            inner_conn = getattr(connection, "connection", None)
            if inner_conn:
                props = inner_conn.server_properties
                if props:
                    version = props.get("version", "unknown")
                    print(f"✓ RabbitMQ version: {version}")

    except Exception as e:
        pytest.fail(f"Failed to connect to RabbitMQ: {e}")
    finally:
        if connection and not connection.is_closed:
            await connection.close()


@pytest.mark.asyncio
async def test_rabbitmq_basic_queue_operations(rabbitmq_url: str) -> None:
    """Test basic RabbitMQ queue operations."""
    print("\nTesting RabbitMQ basic queue operations")

    connection = await aio_pika.connect_robust(rabbitmq_url)

    try:
        channel = await connection.channel()

        # Declare a queue
        queue = await channel.declare_queue("test_queue", auto_delete=True)
        assert queue is not None, "Failed to declare queue"
        print(f"✓ Created queue: {queue.name}")

        # Publish a message
        message_body = b"Hello RabbitMQ"
        await channel.default_exchange.publish(
            Message(body=message_body), routing_key="test_queue"
        )
        print("✓ Published message to queue")

        # Consume the message
        incoming_message = await queue.get(timeout=5.0)
        assert incoming_message is not None, "No message received"
        assert (
            incoming_message.body == message_body
        ), f"Unexpected message: {incoming_message.body!r}"

        # Acknowledge the message
        await incoming_message.ack()
        print(f"✓ Received and acknowledged message: {incoming_message.body.decode()}")

        # Check queue is empty
        try:
            empty_check = await queue.get(timeout=0.5)
            if empty_check:
                await empty_check.nack()
                pytest.fail("Queue should be empty")
        except aio_pika.exceptions.QueueEmpty:
            print("✓ Queue is empty after consumption")
        except asyncio.TimeoutError:
            print("✓ Queue is empty after consumption")

    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_rabbitmq_exchange_types(rabbitmq_url: str) -> None:
    """Test different RabbitMQ exchange types."""
    print("\nTesting RabbitMQ exchange types")

    connection = await aio_pika.connect_robust(rabbitmq_url)

    try:
        channel = await connection.channel()

        # Test Direct Exchange
        direct_exchange = await channel.declare_exchange(
            "test_direct", ExchangeType.DIRECT, auto_delete=True
        )
        print("✓ Created direct exchange")

        # Test Topic Exchange
        topic_exchange = await channel.declare_exchange(
            "test_topic", ExchangeType.TOPIC, auto_delete=True
        )
        print("✓ Created topic exchange")

        # Test Fanout Exchange
        fanout_exchange = await channel.declare_exchange(
            "test_fanout", ExchangeType.FANOUT, auto_delete=True
        )
        print("✓ Created fanout exchange")

        # Create queues and bind them
        direct_queue = await channel.declare_queue("", exclusive=True)
        await direct_queue.bind(direct_exchange, routing_key="direct_key")
        print("✓ Bound queue to direct exchange")

        topic_queue = await channel.declare_queue("", exclusive=True)
        await topic_queue.bind(topic_exchange, routing_key="test.*")
        print("✓ Bound queue to topic exchange with pattern")

        fanout_queue = await channel.declare_queue("", exclusive=True)
        await fanout_queue.bind(fanout_exchange)
        print("✓ Bound queue to fanout exchange")

    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_rabbitmq_topic_routing(rabbitmq_url: str) -> None:
    """Test RabbitMQ topic exchange routing."""
    print("\nTesting RabbitMQ topic routing")

    connection = await aio_pika.connect_robust(rabbitmq_url)

    try:
        channel = await connection.channel()

        # Create topic exchange
        exchange = await channel.declare_exchange(
            "test_topic_routing", ExchangeType.TOPIC, auto_delete=True
        )

        # Create queues with different patterns
        queue1 = await channel.declare_queue("", exclusive=True)
        await queue1.bind(exchange, routing_key="*.error")
        print("✓ Queue1 bound to *.error pattern")

        queue2 = await channel.declare_queue("", exclusive=True)
        await queue2.bind(exchange, routing_key="app.*")
        print("✓ Queue2 bound to app.* pattern")

        queue3 = await channel.declare_queue("", exclusive=True)
        await queue3.bind(exchange, routing_key="app.error")
        print("✓ Queue3 bound to app.error pattern")

        # Publish messages with different routing keys
        await exchange.publish(
            Message(body=b"system error"), routing_key="system.error"
        )
        await exchange.publish(Message(body=b"app error"), routing_key="app.error")
        await exchange.publish(Message(body=b"app info"), routing_key="app.info")

        # Check what each queue received
        await asyncio.sleep(0.1)  # Let messages propagate

        # Queue1 should have 2 messages (*.error matches system.error and app.error)
        msg1 = await queue1.get(timeout=1.0)
        msg2 = await queue1.get(timeout=1.0)
        assert msg1 and msg2, "Queue1 should have 2 messages"
        await msg1.ack()
        await msg2.ack()
        print("✓ Queue1 received 2 messages matching *.error")

        # Queue2 should have 2 messages (app.* matches app.error and app.info)
        msg1 = await queue2.get(timeout=1.0)
        msg2 = await queue2.get(timeout=1.0)
        assert msg1 and msg2, "Queue2 should have 2 messages"
        await msg1.ack()
        await msg2.ack()
        print("✓ Queue2 received 2 messages matching app.*")

        # Queue3 should have 1 message (exact match app.error)
        msg = await queue3.get(timeout=1.0)
        assert msg is not None, "Queue3 should have 1 message"
        assert msg.body == b"app error"
        await msg.ack()
        print("✓ Queue3 received 1 message matching app.error")

    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_rabbitmq_durable_queue(rabbitmq_url: str) -> None:
    """Test RabbitMQ durable queue functionality."""
    print("\nTesting RabbitMQ durable queues")

    # First connection - create queue and publish
    connection1 = await aio_pika.connect_robust(rabbitmq_url)

    try:
        channel1 = await connection1.channel()

        # Declare a durable queue
        queue = await channel1.declare_queue(
            "test_durable_queue", durable=True, auto_delete=False
        )
        print(f"✓ Created durable queue: {queue.name}")

        # Publish a persistent message
        await channel1.default_exchange.publish(
            Message(
                body=b"Persistent message",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="test_durable_queue",
        )
        print("✓ Published persistent message")

        # Close first connection
        await connection1.close()
        print("✓ Closed first connection")

        # Second connection - verify queue and message persist
        connection2 = await aio_pika.connect_robust(rabbitmq_url)
        channel2 = await connection2.channel()

        # Re-declare the queue (should already exist)
        queue2 = await channel2.declare_queue(
            "test_durable_queue",
            durable=True,
            auto_delete=False,
            passive=True,  # Don't create, just check it exists
        )
        print(f"✓ Durable queue still exists: {queue2.name}")

        # Get the message
        message = await queue2.get(timeout=5.0)
        assert message is not None, "Message should persist"
        assert message.body == b"Persistent message"
        await message.ack()
        print("✓ Retrieved persistent message from durable queue")

        # Clean up - delete the queue
        await queue2.delete()
        print("✓ Cleaned up durable queue")

        await connection2.close()

    except Exception as e:
        # Clean up on failure
        try:
            cleanup_conn = await aio_pika.connect_robust(rabbitmq_url)
            cleanup_channel = await cleanup_conn.channel()
            cleanup_queue = await cleanup_channel.declare_queue(
                "test_durable_queue", durable=True, auto_delete=False, passive=True
            )
            await cleanup_queue.delete()
            await cleanup_conn.close()
        except Exception:
            pass  # Queue might not exist or connection might be closed
        raise e


@pytest.mark.asyncio
async def test_rabbitmq_concurrent_consumers(rabbitmq_url: str) -> None:
    """Test multiple consumers on the same queue."""
    print("\nTesting multiple consumers")

    connection = await aio_pika.connect_robust(rabbitmq_url)

    try:
        channel = await connection.channel()

        # Create a queue
        queue = await channel.declare_queue("test_concurrent", auto_delete=True)

        # Publish multiple messages
        num_messages = 10
        for i in range(num_messages):
            await channel.default_exchange.publish(
                Message(body=f"Message {i}".encode()), routing_key="test_concurrent"
            )
        print(f"✓ Published {num_messages} messages")

        # Create multiple consumers
        consumed_messages = []

        async def consume_messages(consumer_id: str, num_to_consume: int) -> None:
            for _ in range(num_to_consume):
                msg = await queue.get(timeout=2.0)
                if msg:
                    consumed_messages.append((consumer_id, msg.body.decode()))
                    await msg.ack()

        # Run consumers concurrently
        await asyncio.gather(
            consume_messages("consumer1", 3),
            consume_messages("consumer2", 3),
            consume_messages("consumer3", 4),
        )

        assert (
            len(consumed_messages) == num_messages
        ), f"Should consume all {num_messages} messages"
        print(f"✓ All {num_messages} messages consumed by multiple consumers")

        # Verify distribution
        consumer_counts: Dict[str, int] = {}
        for consumer_id, _ in consumed_messages:
            consumer_counts[consumer_id] = consumer_counts.get(consumer_id, 0) + 1

        print(f"✓ Message distribution: {consumer_counts}")

    finally:
        await connection.close()
