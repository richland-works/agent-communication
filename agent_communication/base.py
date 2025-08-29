"""Base classes for agent messaging system."""

from abc import ABC, abstractmethod
from typing import List, Type, Callable, Dict, Optional, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from agent_communication.routers.base import AbstractRouter


class BaseMessage(BaseModel, ABC):
    """Base class for all messages in the agent communication system.

    All message types must inherit from this class and implement the
    get_channel_pattern method to define their routing pattern.
    """

    @classmethod
    @abstractmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        """Return a function that generates the channel pattern for this message type.

        The returned function should accept 'direction' and 'session_id' parameters
        and return a formatted channel string.

        Returns:
            A function that takes (direction: str, session_id: str) and returns
            the full channel name.

        Example:
            def pattern_func(direction: str, session_id: str) -> str:
                return f"{cls.__name__}:{direction}:{session_id}"
            return pattern_func
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement get_channel_pattern method"
        )


class BaseAgent(ABC):
    """Base class for all agents in the messaging system.

    Agents must declare which message types they can receive (messages)
    and which message types they can send (sending_messages).

    Agents can optionally be associated with a router for automatic
    subscription management and message publishing.
    """

    messages: List[Type[BaseMessage]] = []
    sending_messages: List[Type[BaseMessage]] = []

    def __init__(self, router: Optional["AbstractRouter"] = None) -> None:
        """Initialize the agent.

        Args:
            router: Optional router for automatic subscription management
        """
        self._router = router
        self._subscribed = False

    @abstractmethod
    def handle_message(self, message: BaseMessage, context: Dict[str, str]) -> None:
        """Handle an incoming message.

        Args:
            message: The message to handle
            context: Additional context including direction and session_id
        """
        pass

    def validate_incoming_message(self, message: BaseMessage) -> bool:
        """Validate that this agent can handle the given message type.

        Args:
            message: The message to validate

        Returns:
            True if the agent can handle this message type, False otherwise
        """
        return type(message) in self.messages

    def validate_outgoing_message(self, message: BaseMessage) -> bool:
        """Validate that this agent is allowed to send the given message type.

        Args:
            message: The message to validate

        Returns:
            True if the agent can send this message type, False otherwise
        """
        return type(message) in self.sending_messages

    async def subscribe(self, pattern: Optional[str] = None) -> None:
        """Subscribe to message channels.

        If no pattern is provided, automatically subscribes based on
        the agent's declared message types.

        Args:
            pattern: Optional specific pattern to subscribe to
        """
        if not self._router:
            raise RuntimeError("No router configured for this agent")

        if pattern:
            await self._router.subscribe(self, pattern)
        else:
            await self._router.auto_subscribe_agent(self)
            self._subscribed = True

    async def unsubscribe(self, pattern: Optional[str] = None) -> None:
        """Unsubscribe from message channels.

        Args:
            pattern: Optional specific pattern to unsubscribe from.
                    If None, unsubscribes from all patterns.
        """
        if not self._router:
            raise RuntimeError("No router configured for this agent")

        await self._router.unsubscribe(self, pattern)
        if not pattern:
            self._subscribed = False

    async def publish(self, message: BaseMessage, channel: str) -> None:
        """Publish a message to a channel.

        Args:
            message: Message to publish
            channel: Channel to publish to
        """
        if not self._router:
            raise RuntimeError("No router configured for this agent")

        if not self.validate_outgoing_message(message):
            raise ValueError(
                f"Agent {self.__class__.__name__} is not allowed to send "
                f"messages of type {message.__class__.__name__}"
            )

        await self._router.publish(message, channel)

    async def broadcast(
        self, message: BaseMessage, direction: str = "response", session_id: str = "*"
    ) -> None:
        """Broadcast a message using its channel pattern.

        Args:
            message: Message to broadcast
            direction: Direction for the channel pattern
            session_id: Session ID for the channel pattern
        """
        if not self._router:
            raise RuntimeError("No router configured for this agent")

        if not self.validate_outgoing_message(message):
            raise ValueError(
                f"Agent {self.__class__.__name__} is not allowed to send "
                f"messages of type {message.__class__.__name__}"
            )

        await self._router.broadcast(message, direction, session_id)

    @property
    def router(self) -> Optional["AbstractRouter"]:
        """Get the agent's router."""
        return self._router

    @router.setter
    def router(self, router: Optional["AbstractRouter"]) -> None:
        """Set the agent's router."""
        self._router = router
