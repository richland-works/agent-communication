"""Test Redis container connectivity and basic operations."""

import pytest
import asyncio
import redis.asyncio as redis
from typing import Optional


@pytest.mark.asyncio
async def test_redis_connection(redis_url: str) -> None:
    """Test that we can connect to Redis container."""
    print(f"\nTesting Redis connection at: {redis_url}")

    client: Optional[redis.Redis[str]] = None
    try:
        client = await redis.from_url(redis_url, decode_responses=True)

        # Test ping
        pong = await client.ping()
        assert pong is True, "Redis ping failed"
        print("✓ Redis connection successful")

        # Get Redis info
        info = await client.info()
        print(
            f"✓ Redis version: {info.get('server', {}).get('redis_version', 'unknown')}"
        )

    except Exception as e:
        pytest.fail(f"Failed to connect to Redis: {e}")
    finally:
        if client:
            await client.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_redis_basic_operations(redis_url: str) -> None:
    """Test basic Redis operations (set/get/delete)."""
    print("\nTesting Redis basic operations")

    client = await redis.from_url(redis_url, decode_responses=True)

    try:
        # Test SET
        result = await client.set("test_key", "test_value")
        assert result is True, "Failed to set key"
        print("✓ SET operation successful")

        # Test GET
        value = await client.get("test_key")
        assert value == "test_value", f"Expected 'test_value', got {value}"
        print("✓ GET operation successful")

        # Test EXISTS
        exists = await client.exists("test_key")
        assert exists == 1, "Key should exist"
        print("✓ EXISTS operation successful")

        # Test DELETE
        deleted = await client.delete("test_key")
        assert deleted == 1, "Failed to delete key"
        print("✓ DELETE operation successful")

        # Verify deletion
        value = await client.get("test_key")
        assert value is None, "Key should be deleted"
        print("✓ Key successfully deleted")

    finally:
        await client.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_redis_pubsub_basic(redis_url: str) -> None:
    """Test Redis Pub/Sub functionality."""
    print("\nTesting Redis Pub/Sub")

    # Create publisher and subscriber clients
    pub_client = await redis.from_url(redis_url, decode_responses=False)
    sub_client = await redis.from_url(redis_url, decode_responses=False)

    try:
        # Create pubsub object
        pubsub = sub_client.pubsub()

        # Subscribe to a channel
        await pubsub.subscribe("test_channel")
        print("✓ Subscribed to test_channel")

        # Give subscription time to register
        await asyncio.sleep(0.1)

        # Publish a message
        num_subscribers = await pub_client.publish("test_channel", b"hello_world")
        print(f"✓ Published message to {num_subscribers} subscriber(s)")
        assert num_subscribers >= 1, "Message should have at least one subscriber"

        # Try to receive the message
        message_received = False

        async def get_message() -> None:
            nonlocal message_received
            async for message in pubsub.listen():
                print(f"  Received message type: {message['type']}")
                if message["type"] == "subscribe":
                    # Skip subscription confirmation
                    continue
                elif message["type"] == "message":
                    assert (
                        message["data"] == b"hello_world"
                    ), f"Unexpected message data: {message['data']}"
                    message_received = True
                    print(f"✓ Received correct message: {message['data']}")
                    return

        # Wait for message with timeout
        try:
            await asyncio.wait_for(get_message(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail(
                "Timeout waiting for message - Redis Pub/Sub may not be working"
            )

        assert message_received, "Message was not received"

        # Unsubscribe
        await pubsub.unsubscribe("test_channel")
        print("✓ Unsubscribed from test_channel")

    finally:
        if pubsub:
            await pubsub.aclose()  # type: ignore[attr-defined]
        await pub_client.aclose()  # type: ignore[attr-defined]
        await sub_client.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_redis_pubsub_patterns(redis_url: str) -> None:
    """Test Redis pattern subscriptions."""
    print("\nTesting Redis pattern subscriptions")

    pub_client = await redis.from_url(redis_url, decode_responses=False)
    sub_client = await redis.from_url(redis_url, decode_responses=False)

    try:
        pubsub = sub_client.pubsub()

        # Subscribe to a pattern
        await pubsub.psubscribe("test:*")
        print("✓ Pattern subscribed to test:*")

        await asyncio.sleep(0.1)

        # Publish to matching channels
        await pub_client.publish("test:channel1", b"message1")
        await pub_client.publish("test:channel2", b"message2")
        await pub_client.publish("other:channel", b"should_not_receive")

        # Collect messages
        received_messages = []

        async def collect_messages() -> None:
            count = 0
            async for message in pubsub.listen():
                if message["type"] == "psubscribe":
                    continue
                elif message["type"] == "pmessage":
                    received_messages.append(
                        {
                            "channel": message["channel"].decode()
                            if isinstance(message["channel"], bytes)
                            else message["channel"],
                            "data": message["data"],
                        }
                    )
                    count += 1
                    if count >= 2:  # Expect 2 messages
                        return

        try:
            await asyncio.wait_for(collect_messages(), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # It's okay if we timeout after receiving some messages

        # Verify we got the right messages
        assert (
            len(received_messages) == 2
        ), f"Expected 2 messages, got {len(received_messages)}"

        channels = [msg["channel"] for msg in received_messages]
        assert "test:channel1" in channels
        assert "test:channel2" in channels
        assert "other:channel" not in channels

        print(f"✓ Received {len(received_messages)} messages on pattern subscription")

    finally:
        if pubsub:
            await pubsub.aclose()  # type: ignore[attr-defined]
        await pub_client.aclose()  # type: ignore[attr-defined]
        await sub_client.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_redis_multiple_subscribers(redis_url: str) -> None:
    """Test multiple subscribers to the same channel."""
    print("\nTesting multiple subscribers")

    pub_client = await redis.from_url(redis_url, decode_responses=False)
    sub_client1 = await redis.from_url(redis_url, decode_responses=False)
    sub_client2 = await redis.from_url(redis_url, decode_responses=False)

    try:
        # Create two subscribers
        pubsub1 = sub_client1.pubsub()
        pubsub2 = sub_client2.pubsub()

        await pubsub1.subscribe("shared_channel")
        await pubsub2.subscribe("shared_channel")

        await asyncio.sleep(0.1)

        # Publish a message
        num_subscribers = await pub_client.publish(
            "shared_channel", b"broadcast_message"
        )
        print(f"✓ Published to {num_subscribers} subscribers")
        assert num_subscribers == 2, f"Expected 2 subscribers, got {num_subscribers}"

        # Both should receive the message
        messages_received = []

        async def receive_from_pubsub(pubsub: redis.client.PubSub, name: str) -> None:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    messages_received.append(name)
                    return

        # Wait for both to receive
        await asyncio.gather(
            asyncio.wait_for(receive_from_pubsub(pubsub1, "sub1"), timeout=2.0),
            asyncio.wait_for(receive_from_pubsub(pubsub2, "sub2"), timeout=2.0),
        )

        assert (
            len(messages_received) == 2
        ), "Both subscribers should receive the message"
        assert "sub1" in messages_received
        assert "sub2" in messages_received
        print("✓ Both subscribers received the message")

    finally:
        if pubsub1:
            await pubsub1.aclose()  # type: ignore[attr-defined]
        if pubsub2:
            await pubsub2.aclose()  # type: ignore[attr-defined]
        await pub_client.aclose()  # type: ignore[attr-defined]
        await sub_client1.aclose()  # type: ignore[attr-defined]
        await sub_client2.aclose()  # type: ignore[attr-defined]
