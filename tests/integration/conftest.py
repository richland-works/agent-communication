"""Pytest configuration for integration tests."""

import asyncio
import time
import pytest
import pytest_asyncio
from typing import AsyncGenerator
import redis.asyncio as redis
import aio_pika
from testcontainers.redis import RedisContainer
from testcontainers.rabbitmq import RabbitMqContainer


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    """Set the event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def redis_container() -> AsyncGenerator[RedisContainer, None]:
    """Start a Redis container for testing with health checks."""
    print("\n🚀 Starting Redis container...")

    with RedisContainer("redis:7-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        url = f"redis://{host}:{port}/0"

        # Wait for Redis to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                # Test connection
                client = await redis.from_url(url)
                await client.ping()
                await client.aclose()  # type: ignore[attr-defined]
                print(f"✅ Redis container ready at {host}:{port}")
                break
            except Exception as e:
                if i == max_retries - 1:
                    print(f"❌ Redis container failed to start: {e}")
                    raise
                time.sleep(1)

        yield container


@pytest_asyncio.fixture(scope="session")
async def rabbitmq_container() -> AsyncGenerator[RabbitMqContainer, None]:
    """Start a RabbitMQ container for testing with health checks."""
    print("\n🚀 Starting RabbitMQ container...")

    with RabbitMqContainer("rabbitmq:3.12-management-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5672)
        username = container.username if hasattr(container, "username") else "guest"
        password = container.password if hasattr(container, "password") else "guest"
        url = f"amqp://{username}:{password}@{host}:{port}/"

        # Wait for RabbitMQ to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                # Test connection
                connection = await aio_pika.connect_robust(url)
                await connection.close()
                print(f"✅ RabbitMQ container ready at {host}:{port}")
                break
            except Exception as e:
                if i == max_retries - 1:
                    print(f"❌ RabbitMQ container failed to start: {e}")
                    raise
                time.sleep(1)

        yield container


@pytest_asyncio.fixture
async def redis_url(redis_container: RedisContainer) -> str:
    """Get the Redis connection URL with validation."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    url = f"redis://{host}:{port}/0"

    # Validate connection before returning
    try:
        client = await redis.from_url(url)
        await client.ping()
        await client.aclose()  # type: ignore[attr-defined]
        return url
    except Exception as e:
        pytest.fail(f"Redis not accessible at {url}: {e}")
        raise  # Never reached, but satisfies mypy


@pytest_asyncio.fixture
async def rabbitmq_url(rabbitmq_container: RabbitMqContainer) -> str:
    """Get the RabbitMQ connection URL with validation."""
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    username = (
        rabbitmq_container.username
        if hasattr(rabbitmq_container, "username")
        else "guest"
    )
    password = (
        rabbitmq_container.password
        if hasattr(rabbitmq_container, "password")
        else "guest"
    )
    url = f"amqp://{username}:{password}@{host}:{port}/"

    # Validate connection before returning
    try:
        connection = await aio_pika.connect_robust(url)
        await connection.close()
        return url
    except Exception as e:
        pytest.fail(f"RabbitMQ not accessible at {url}: {e}")
        raise  # Never reached, but satisfies mypy


@pytest_asyncio.fixture(autouse=True)
async def cleanup_between_tests() -> AsyncGenerator[None, None]:
    """Ensure clean state between tests."""
    # Run test
    yield

    # Cancel any pending tasks from the test
    loop = asyncio.get_event_loop()
    pending = asyncio.all_tasks(loop)
    current_task = asyncio.current_task(loop)

    # Cancel all tasks except the current cleanup task
    for task in pending:
        if task != current_task and not task.done():
            task.cancel()

    # Wait for cancellations to complete
    if pending:
        await asyncio.gather(
            *[t for t in pending if t != current_task], return_exceptions=True
        )

    # Add small delay between tests to prevent race conditions
    await asyncio.sleep(0.1)
