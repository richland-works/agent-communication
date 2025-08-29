"""Redis-based message router implementation."""

import asyncio
from typing import Optional, Dict, Any
import redis.asyncio as redis
from redis.asyncio.client import PubSub
from agent_communication.routers.base import AbstractRouter


class RedisRouter(AbstractRouter):
    """Redis Pub/Sub based message router.

    Uses Redis Pub/Sub for lightweight, real-time message routing.
    Supports pattern subscriptions with wildcards for flexible routing.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        url: Optional[str] = None,
        **redis_kwargs: Any,
    ) -> None:
        """Initialize Redis router.

        Args:
            host: Redis host address
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            url: Redis URL (overrides host/port/db/password)
            **redis_kwargs: Additional Redis client arguments
        """
        super().__init__()

        if url:
            self._redis_url = url
        else:
            self._redis_url = f"redis://{host}:{port}/{db}"
            if password:
                self._redis_url = f"redis://:{password}@{host}:{port}/{db}"

        self._redis_kwargs = redis_kwargs
        self._redis: Optional[redis.Redis[bytes]] = None
        self._pubsub: Optional[PubSub] = None
        self._listener_task: Optional[asyncio.Task[None]] = None
        self._subscribed_patterns: set[str] = set()

    async def connect(self) -> None:
        """Connect to Redis server."""
        try:
            self._redis = await redis.from_url(
                self._redis_url, decode_responses=False, **self._redis_kwargs
            )

            await self._redis.ping()

            self._pubsub = self._redis.pubsub()

            self._listener_task = asyncio.create_task(self._message_listener())

            self.logger.info(f"Connected to Redis at {self._redis_url}")

        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis server."""
        try:
            # Cancel the listener task
            if self._listener_task:
                self._listener_task.cancel()
                try:
                    await asyncio.wait_for(self._listener_task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            # Unsubscribe and close pubsub
            if self._pubsub:
                try:
                    await self._pubsub.unsubscribe()
                    await self._pubsub.aclose()  # type: ignore[attr-defined]  # Use aclose() instead of close()
                except Exception as e:
                    self.logger.debug(f"Error closing pubsub: {e}")

            # Close Redis connection
            if self._redis:
                try:
                    await self._redis.aclose()  # type: ignore[attr-defined]  # Use aclose() instead of close()
                    # Wait for connection pool to close
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"Error closing Redis connection: {e}")

            # Clear all references
            self._redis = None
            self._pubsub = None
            self._listener_task = None
            self._subscribed_patterns.clear()

            self.logger.info("Disconnected from Redis")

        except Exception as e:
            self.logger.error(f"Error disconnecting from Redis: {e}")

    async def _publish_raw(self, channel: str, data: bytes) -> None:
        """Publish raw message data to a Redis channel.

        Args:
            channel: Channel name to publish to
            data: Serialized message data
        """
        if not self._redis:
            raise RuntimeError("Router not connected")

        try:
            await self._redis.publish(channel, data)
            self.logger.debug(f"Published message to Redis channel: {channel}")
        except Exception as e:
            self.logger.error(f"Error publishing to Redis: {e}")
            raise

    async def _subscribe_raw(self, pattern: str) -> None:
        """Subscribe to a channel pattern in Redis.

        Args:
            pattern: Channel pattern to subscribe to (may include wildcards)
        """
        if not self._pubsub:
            raise RuntimeError("Router not connected")

        if pattern in self._subscribed_patterns:
            return

        try:
            if "*" in pattern or "?" in pattern or "[" in pattern:
                await self._pubsub.psubscribe(pattern)
                self.logger.debug(f"Pattern subscribed to Redis: {pattern}")
            else:
                await self._pubsub.subscribe(pattern)
                self.logger.debug(f"Subscribed to Redis channel: {pattern}")

            self._subscribed_patterns.add(pattern)

            # Give the subscription time to register
            await asyncio.sleep(0.01)

        except Exception as e:
            self.logger.error(f"Error subscribing to Redis: {e}")
            raise

    async def _unsubscribe_raw(self, pattern: str) -> None:
        """Unsubscribe from a channel pattern in Redis.

        Args:
            pattern: Channel pattern to unsubscribe from
        """
        if not self._pubsub:
            raise RuntimeError("Router not connected")

        if pattern not in self._subscribed_patterns:
            return

        try:
            if "*" in pattern or "?" in pattern or "[" in pattern:
                await self._pubsub.punsubscribe(pattern)
                self.logger.debug(f"Pattern unsubscribed from Redis: {pattern}")
            else:
                await self._pubsub.unsubscribe(pattern)
                self.logger.debug(f"Unsubscribed from Redis channel: {pattern}")

            self._subscribed_patterns.discard(pattern)

        except Exception as e:
            self.logger.error(f"Error unsubscribing from Redis: {e}")
            raise

    async def _message_listener(self) -> None:
        """Listen for messages from Redis Pub/Sub."""
        if not self._pubsub:
            return

        # Track delivered messages to avoid duplicates from multiple pattern matches
        delivered_messages: Dict[tuple[str, bytes], float] = {}

        try:
            self.logger.debug("Starting message listener loop")
            while True:
                try:
                    # Use get_message with timeout instead of async for
                    message = await self._pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=0.01
                    )

                    if message is None:
                        # No message available, continue
                        await asyncio.sleep(0.01)
                        # Clean up old delivered messages (older than 5 seconds)
                        current_time = asyncio.get_event_loop().time()
                        delivered_messages = {
                            k: v
                            for k, v in delivered_messages.items()
                            if current_time - v < 5.0
                        }
                        continue

                    self.logger.info(f"Raw Redis message: {message}")

                    if message["type"] in ("message", "pmessage"):
                        # For pmessage, 'channel' is the actual channel and 'pattern' is the subscription pattern
                        if message["type"] == "pmessage":
                            channel = message[
                                "channel"
                            ]  # Actual channel like "SampleMessage:request:session123"
                            pattern = message.get("pattern")
                        else:
                            channel = message["channel"]  # Direct subscription channel
                            pattern = None

                        if isinstance(channel, bytes):
                            channel = channel.decode("utf-8")

                        data = message["data"]
                        if isinstance(data, str):
                            data = data.encode("utf-8")
                        elif isinstance(data, bytes):
                            pass  # Already bytes
                        else:
                            self.logger.warning(
                                f"Skipping non-data message: {type(data)}"
                            )
                            continue  # Skip non-data messages

                        # Check if we've already delivered this message
                        message_key = (channel, data)
                        current_time = asyncio.get_event_loop().time()

                        if message_key in delivered_messages:
                            self.logger.debug(
                                f"Skipping duplicate message on channel {channel} from pattern {pattern}"
                            )
                            continue

                        delivered_messages[message_key] = current_time

                        self.logger.info(
                            f"Received message from Redis channel: {channel}, data length: {len(data)}"
                        )

                        try:
                            await self.deliver_message(channel, data)
                        except Exception as e:
                            self.logger.error(
                                f"Error delivering message: {e}", exc_info=True
                            )

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.debug(f"Error getting message: {e}")
                    await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            self.logger.debug("Message listener cancelled")
        except Exception as e:
            self.logger.error(f"Error in message listener: {e}", exc_info=True)

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._redis:
            return False

        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
