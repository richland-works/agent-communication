"""RabbitMQ-based message router implementation."""

import asyncio
from typing import Optional, Dict, Any
import aio_pika
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractIncomingMessage,
)
from agent_communication.routers.base import AbstractRouter


class RabbitMQRouter(AbstractRouter):
    """RabbitMQ AMQP-based message router.

    Uses RabbitMQ topic exchanges for flexible message routing with
    pattern matching. Provides durable queues and message acknowledgments
    for reliable message delivery.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        vhost: str = "/",
        exchange_name: str = "agent_communication",
        url: Optional[str] = None,
        **amqp_kwargs: Any,
    ) -> None:
        """Initialize RabbitMQ router.

        Args:
            host: RabbitMQ host address
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            vhost: RabbitMQ virtual host
            exchange_name: Name of the topic exchange to use
            url: AMQP URL (overrides host/port/username/password/vhost)
            **amqp_kwargs: Additional AMQP connection arguments
        """
        super().__init__()

        if url:
            self._amqp_url = url
        else:
            self._amqp_url = f"amqp://{username}:{password}@{host}:{port}{vhost}"

        self._exchange_name = exchange_name
        self._amqp_kwargs = amqp_kwargs
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._exchange: Optional[AbstractExchange] = None
        self._queues: Dict[str, AbstractQueue] = {}
        self._consumers: Dict[str, Any] = {}

        # Track delivered messages to avoid duplicates from multiple bindings
        self._delivered_messages: Dict[tuple[str, bytes], float] = {}
        self._cleanup_task: Optional[asyncio.Task[None]] = None

    async def connect(self) -> None:
        """Connect to RabbitMQ server."""
        try:
            self._connection = await aio_pika.connect_robust(
                self._amqp_url, **self._amqp_kwargs
            )

            self._channel = await self._connection.channel()

            await self._channel.set_qos(prefetch_count=10)

            self._exchange = await self._channel.declare_exchange(
                self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
            )

            self.logger.info(f"Connected to RabbitMQ at {self._amqp_url}")

        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ server without deleting queues.

        This preserves queues and messages for reconnection.
        Use stop() to fully clean up including queue deletion.
        """
        try:
            # Cancel consumers but don't delete queues
            for pattern, consumer_tag in list(self._consumers.items()):
                try:
                    if pattern in self._queues:
                        await self._queues[pattern].cancel(consumer_tag)
                except Exception as e:
                    self.logger.debug(f"Error canceling consumer for {pattern}: {e}")

            # Close the channel
            if self._channel and not self._channel.is_closed:
                try:
                    await self._channel.close()
                except Exception as e:
                    self.logger.debug(f"Error closing channel: {e}")

            # Close the connection
            if self._connection and not self._connection.is_closed:
                try:
                    await self._connection.close()
                    # Give connection time to close gracefully
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"Error closing connection: {e}")

            # Clear references but keep queue info for reconnection
            self._channel = None
            self._connection = None
            self._exchange = None
            self._queues.clear()
            self._consumers.clear()

            self.logger.info("Disconnected from RabbitMQ (queues preserved)")

        except Exception as e:
            self.logger.error(f"Error disconnecting from RabbitMQ: {e}")

    async def _publish_raw(self, channel: str, data: bytes) -> None:
        """Publish raw message data to a RabbitMQ routing key.

        Args:
            channel: Routing key to publish to
            data: Serialized message data
        """
        if not self._exchange:
            raise RuntimeError("Router not connected")

        try:
            routing_key = self._channel_to_routing_key(channel)

            message = aio_pika.Message(
                body=data,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )

            await self._exchange.publish(message, routing_key=routing_key)

            self.logger.debug(
                f"Published message to RabbitMQ routing key: {routing_key}"
            )

        except Exception as e:
            self.logger.error(f"Error publishing to RabbitMQ: {e}")
            raise

    async def _subscribe_raw(self, pattern: str) -> None:
        """Subscribe to a channel pattern in RabbitMQ.

        Args:
            pattern: Channel pattern to subscribe to (may include wildcards)
        """
        if not self._channel or not self._exchange:
            raise RuntimeError("Router not connected")

        if pattern in self._queues:
            return

        try:
            # Use a deterministic queue name based on the pattern
            # This allows reconnection to the same queue for persistence
            import hashlib

            pattern_hash = hashlib.md5(pattern.encode()).hexdigest()[:8]
            queue_name = f"agent_communication.{pattern.replace(':', '.').replace('*', 'star')}.{pattern_hash}"

            # All queues are durable but not auto-delete for persistence
            queue = await self._channel.declare_queue(
                queue_name, durable=True, auto_delete=False
            )

            routing_pattern = self._channel_to_routing_key(pattern)
            routing_pattern = routing_pattern.replace("*", "#")

            await queue.bind(self._exchange, routing_key=routing_pattern)

            self._queues[pattern] = queue

            consumer = await queue.consume(self._message_callback, no_ack=False)
            self._consumers[pattern] = consumer

            self.logger.debug(f"Subscribed to RabbitMQ pattern: {routing_pattern}")

        except Exception as e:
            self.logger.error(f"Error subscribing to RabbitMQ: {e}")
            raise

    async def _unsubscribe_raw(self, pattern: str) -> None:
        """Unsubscribe from a channel pattern in RabbitMQ.

        Args:
            pattern: Channel pattern to unsubscribe from
        """
        if pattern not in self._queues:
            return

        try:
            if pattern in self._consumers:
                await self._queues[pattern].cancel(self._consumers[pattern])
                del self._consumers[pattern]

            if pattern in self._queues:
                await self._queues[pattern].delete(if_unused=True, if_empty=True)
                del self._queues[pattern]

            self.logger.debug(f"Unsubscribed from RabbitMQ pattern: {pattern}")

        except Exception as e:
            self.logger.error(f"Error unsubscribing from RabbitMQ: {e}")

    async def _message_callback(self, message: AbstractIncomingMessage) -> None:
        """Handle incoming messages from RabbitMQ.

        Args:
            message: Incoming AMQP message
        """
        try:
            async with message.process():
                routing_key = message.routing_key or ""
                channel = self._routing_key_to_channel(routing_key)
                data = message.body

                # Check for duplicate messages from multiple bindings
                message_key = (channel, data)
                current_time = asyncio.get_event_loop().time()

                # Clean up old entries (older than 5 seconds)
                self._delivered_messages = {
                    k: v
                    for k, v in self._delivered_messages.items()
                    if current_time - v < 5.0
                }

                if message_key in self._delivered_messages:
                    self.logger.debug(
                        f"Skipping duplicate message on channel {channel}"
                    )
                    return

                self._delivered_messages[message_key] = current_time

                self.logger.debug(f"Received message from RabbitMQ: {channel}")

                await self.deliver_message(channel, data)

        except Exception as e:
            self.logger.error(f"Error processing RabbitMQ message: {e}")
            await message.nack(requeue=True)

    def _channel_to_routing_key(self, channel: str) -> str:
        """Convert channel name to RabbitMQ routing key.

        Args:
            channel: Channel name

        Returns:
            RabbitMQ routing key
        """
        return channel.replace(":", ".")

    def _routing_key_to_channel(self, routing_key: str) -> str:
        """Convert RabbitMQ routing key to channel name.

        Args:
            routing_key: RabbitMQ routing key

        Returns:
            Channel name
        """
        return routing_key.replace(".", ":")

    async def stop(self) -> None:
        """Stop the router and fully clean up including queue deletion."""
        if self._running:
            self._running = False

            # Delete all queues before disconnecting
            for pattern in list(self._queues.keys()):
                try:
                    await self._unsubscribe_raw(pattern)
                except Exception as e:
                    self.logger.debug(f"Error unsubscribing {pattern}: {e}")

            # Clear subscriptions
            async with self._lock:
                self._subscriptions.clear()
                self._agent_subscriptions.clear()

            # Disconnect from backend
            try:
                await self.disconnect()
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")

            self.logger.info(f"{self.__class__.__name__} stopped")

    async def health_check(self) -> bool:
        """Check if RabbitMQ connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._connection or not self._channel:
            return False

        try:
            return not self._connection.is_closed and not self._channel.is_closed
        except Exception:
            return False

    async def purge_queue(self, pattern: str) -> int:
        """Purge all messages from a queue.

        Args:
            pattern: Pattern identifying the queue

        Returns:
            Number of messages purged
        """
        if pattern in self._queues:
            result = await self._queues[pattern].purge()
            count = result.message_count
            return (
                int(count) if count is not None else 0
            )  # Extract count from PurgeOk object
        return 0
