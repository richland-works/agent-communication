"""Abstract base class for message routers."""

from abc import ABC, abstractmethod
from typing import Dict, Set, Optional, Type, List
import asyncio
from agent_communication.base import BaseMessage, BaseAgent
from agent_communication.logger import get_logger


class AbstractRouter(ABC):
    """Abstract base class for message routers.

    Routers handle subscription management, message routing, and broadcasting
    to multiple agents. Concrete implementations use different backends
    (Redis, RabbitMQ, etc.) for message transport.
    """

    def __init__(self) -> None:
        """Initialize the router."""
        self.logger = get_logger(self.__class__.__name__)
        self._subscriptions: Dict[str, Set[BaseAgent]] = {}
        self._agent_subscriptions: Dict[BaseAgent, Set[str]] = {}
        self._running = False
        self._lock = asyncio.Lock()

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the message broker backend."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message broker backend."""
        pass

    @abstractmethod
    async def _publish_raw(self, channel: str, data: bytes) -> None:
        """Publish raw message data to a channel.

        Args:
            channel: Channel name to publish to
            data: Serialized message data
        """
        pass

    @abstractmethod
    async def _subscribe_raw(self, pattern: str) -> None:
        """Subscribe to a channel pattern in the backend.

        Args:
            pattern: Channel pattern to subscribe to (may include wildcards)
        """
        pass

    @abstractmethod
    async def _unsubscribe_raw(self, pattern: str) -> None:
        """Unsubscribe from a channel pattern in the backend.

        Args:
            pattern: Channel pattern to unsubscribe from
        """
        pass

    async def subscribe(self, agent: BaseAgent, pattern: str) -> None:
        """Subscribe an agent to a channel pattern.

        Args:
            agent: Agent to subscribe
            pattern: Channel pattern to subscribe to (may include wildcards)
        """
        async with self._lock:
            if pattern not in self._subscriptions:
                self._subscriptions[pattern] = set()
                await self._subscribe_raw(pattern)

            self._subscriptions[pattern].add(agent)

            if agent not in self._agent_subscriptions:
                self._agent_subscriptions[agent] = set()
            self._agent_subscriptions[agent].add(pattern)

            self.logger.info(
                f"Agent {agent.__class__.__name__} subscribed to {pattern}"
            )

    async def unsubscribe(
        self, agent: BaseAgent, pattern: Optional[str] = None
    ) -> None:
        """Unsubscribe an agent from channel patterns.

        Args:
            agent: Agent to unsubscribe
            pattern: Specific pattern to unsubscribe from. If None, unsubscribe from all.
        """
        async with self._lock:
            if pattern:
                patterns = [pattern]
            else:
                patterns = list(self._agent_subscriptions.get(agent, []))

            for pat in patterns:
                if pat in self._subscriptions and agent in self._subscriptions[pat]:
                    self._subscriptions[pat].remove(agent)

                    if not self._subscriptions[pat]:
                        del self._subscriptions[pat]
                        await self._unsubscribe_raw(pat)

                if agent in self._agent_subscriptions:
                    self._agent_subscriptions[agent].discard(pat)

            if (
                agent in self._agent_subscriptions
                and not self._agent_subscriptions[agent]
            ):
                del self._agent_subscriptions[agent]

            self.logger.info(
                f"Agent {agent.__class__.__name__} unsubscribed from {pattern or 'all patterns'}"
            )

    async def publish(self, message: BaseMessage, channel: str) -> None:
        """Publish a message to a specific channel.

        Args:
            message: Message to publish
            channel: Channel name to publish to
        """
        data = self._serialize_message(message)
        await self._publish_raw(channel, data)

        self.logger.debug(f"Published {message.__class__.__name__} to {channel}")

    async def broadcast(
        self, message: BaseMessage, direction: str, session_id: str
    ) -> None:
        """Broadcast a message using its channel pattern.

        Args:
            message: Message to broadcast
            direction: Direction for the channel pattern (e.g., 'request', 'response')
            session_id: Session ID for the channel pattern
        """
        pattern_func = message.get_channel_pattern()
        channel = pattern_func(direction, session_id)
        await self.publish(message, channel)

    async def deliver_message(self, channel: str, data: bytes) -> None:
        """Deliver a message to subscribed agents.

        Called by concrete implementations when messages are received.

        Args:
            channel: Channel the message was received on
            data: Serialized message data
        """
        message = self._deserialize_message(data)
        context = self._parse_channel_context(channel)

        agents_to_notify: Set[BaseAgent] = set()

        for pattern, agents in self._subscriptions.items():
            if self._matches_pattern(channel, pattern):
                agents_to_notify.update(agents)

        tasks = []
        for agent in agents_to_notify:
            if agent.validate_incoming_message(message):
                tasks.append(self._deliver_to_agent(agent, message, context))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver_to_agent(
        self, agent: BaseAgent, message: BaseMessage, context: Dict[str, str]
    ) -> None:
        """Deliver a message to a specific agent.

        Args:
            agent: Agent to deliver to
            message: Message to deliver
            context: Message context
        """
        try:
            if asyncio.iscoroutinefunction(agent.handle_message):
                await agent.handle_message(message, context)
            else:
                agent.handle_message(message, context)

            self.logger.debug(
                f"Delivered {message.__class__.__name__} to {agent.__class__.__name__}"
            )
        except Exception as e:
            self.logger.error(
                f"Error delivering message to {agent.__class__.__name__}: {e}"
            )

    def _serialize_message(self, message: BaseMessage) -> bytes:
        """Serialize a message to bytes.

        Args:
            message: Message to serialize

        Returns:
            Serialized message data
        """
        import json

        data = message.model_dump()
        data["__type__"] = message.__class__.__name__
        return json.dumps(data).encode("utf-8")

    def _deserialize_message(self, data: bytes) -> BaseMessage:
        """Deserialize message data.

        Args:
            data: Serialized message data

        Returns:
            Deserialized message
        """
        import json

        message_dict = json.loads(data)

        message_type = message_dict.get("__type__")
        if not message_type:
            raise ValueError("Message data missing __type__ field")

        # Get all message types from subscribed agents
        message_classes = {}
        for agents in self._subscriptions.values():
            for agent in agents:
                for msg_class in agent.messages:
                    message_classes[msg_class.__name__] = msg_class

        # Try to find the message class
        if message_type in message_classes:
            del message_dict["__type__"]
            return message_classes[message_type](**message_dict)

        # Fallback to checking BaseMessage subclasses
        from agent_communication.base import BaseMessage

        def get_all_subclasses(cls: Type[BaseMessage]) -> List[Type[BaseMessage]]:
            all_subclasses: List[Type[BaseMessage]] = []
            for subclass in cls.__subclasses__():
                all_subclasses.append(subclass)
                all_subclasses.extend(get_all_subclasses(subclass))
            return all_subclasses

        for subclass in get_all_subclasses(BaseMessage):  # type: ignore[type-abstract]
            if subclass.__name__ == message_type:
                del message_dict["__type__"]
                return subclass(**message_dict)

        raise ValueError(f"Unknown message type: {message_type}")

    def _parse_channel_context(self, channel: str) -> Dict[str, str]:
        """Parse channel name into context dictionary.

        Args:
            channel: Channel name

        Returns:
            Context dictionary with channel components
        """
        from agent_communication.utils import parse_channel

        return parse_channel(channel)

    def _matches_pattern(self, channel: str, pattern: str) -> bool:
        """Check if a channel matches a subscription pattern.

        Args:
            channel: Channel name
            pattern: Subscription pattern (may include wildcards)

        Returns:
            True if channel matches pattern
        """
        if "*" not in pattern:
            return channel == pattern

        import re

        regex_pattern = pattern.replace("*", ".*")
        regex_pattern = f"^{regex_pattern}$"
        return bool(re.match(regex_pattern, channel))

    async def start(self) -> None:
        """Start the router and connect to backend."""
        if not self._running:
            await self.connect()
            self._running = True
            self.logger.info(f"{self.__class__.__name__} started")

    async def stop(self) -> None:
        """Stop the router and disconnect from backend."""
        if self._running:
            self._running = False

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

    async def auto_subscribe_agent(self, agent: BaseAgent) -> None:
        """Automatically subscribe an agent based on its declared message types.

        Args:
            agent: Agent to auto-subscribe
        """
        for message_class in agent.messages:
            pattern_func = message_class.get_channel_pattern()
            pattern = pattern_func("*", "*")
            await self.subscribe(agent, pattern)
