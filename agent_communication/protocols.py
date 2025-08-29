"""Protocol definitions for flexible agent and message implementations."""

from typing import (
    Protocol,
    runtime_checkable,
    List,
    Type,
    Dict,
    Callable,
    Optional,
    Any,
)


@runtime_checkable
class MessageProtocol(Protocol):
    """Protocol for message implementations.

    This protocol defines the interface that all messages must implement.
    Users can either inherit from BaseMessage or implement this protocol
    directly in their own classes.
    """

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        """Return a function that generates the channel pattern for this message type.

        Returns:
            A function that takes (direction: str, session_id: str) and returns
            the full channel name.
        """
        ...

    def model_dump(self) -> Dict[str, Any]:
        """Dump the message to a dictionary.

        Returns:
            Dictionary representation of the message
        """
        ...

    def model_dump_json(self) -> str:
        """Dump the message to a JSON string.

        Returns:
            JSON string representation of the message
        """
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol for agent implementations.

    This protocol defines the interface that all agents must implement.
    Users can either inherit from BaseAgent or implement this protocol
    directly in their own classes.
    """

    messages: List[Type[MessageProtocol]]
    sending_messages: List[Type[MessageProtocol]]

    def handle_message(self, message: MessageProtocol, context: Dict[str, str]) -> None:
        """Handle an incoming message.

        Args:
            message: The message to handle
            context: Additional context including direction and session_id
        """
        ...

    def validate_incoming_message(self, message: MessageProtocol) -> bool:
        """Validate that this agent can handle the given message type.

        Args:
            message: The message to validate

        Returns:
            True if the agent can handle this message type
        """
        ...

    def validate_outgoing_message(self, message: MessageProtocol) -> bool:
        """Validate that this agent is allowed to send the given message type.

        Args:
            message: The message to validate

        Returns:
            True if the agent can send this message type
        """
        ...


@runtime_checkable
class RouterProtocol(Protocol):
    """Protocol for router implementations.

    This protocol defines the interface that all routers must implement.
    """

    async def connect(self) -> None:
        """Connect to the message broker backend."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the message broker backend."""
        ...

    async def subscribe(self, agent: AgentProtocol, pattern: str) -> None:
        """Subscribe an agent to a channel pattern.

        Args:
            agent: Agent to subscribe
            pattern: Channel pattern to subscribe to
        """
        ...

    async def unsubscribe(
        self, agent: AgentProtocol, pattern: Optional[str] = None
    ) -> None:
        """Unsubscribe an agent from channel patterns.

        Args:
            agent: Agent to unsubscribe
            pattern: Specific pattern to unsubscribe from
        """
        ...

    async def publish(self, message: MessageProtocol, channel: str) -> None:
        """Publish a message to a specific channel.

        Args:
            message: Message to publish
            channel: Channel name to publish to
        """
        ...

    async def broadcast(
        self, message: MessageProtocol, direction: str, session_id: str
    ) -> None:
        """Broadcast a message using its channel pattern.

        Args:
            message: Message to broadcast
            direction: Direction for the channel pattern
            session_id: Session ID for the channel pattern
        """
        ...

    async def start(self) -> None:
        """Start the router and connect to backend."""
        ...

    async def stop(self) -> None:
        """Stop the router and disconnect from backend."""
        ...


class MessageMixin:
    """Mixin class that provides message functionality.

    This can be mixed into existing user classes to add message capabilities
    without requiring direct inheritance from BaseMessage.
    """

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        """Default channel pattern implementation."""

        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class AgentMixin:
    """Mixin class that provides agent functionality.

    This can be mixed into existing user classes to add agent capabilities
    without requiring direct inheritance from BaseAgent.
    """

    messages: List[Type[MessageProtocol]] = []
    sending_messages: List[Type[MessageProtocol]] = []

    def validate_incoming_message(self, message: MessageProtocol) -> bool:
        """Validate that this agent can handle the given message type."""
        return type(message) in self.messages

    def validate_outgoing_message(self, message: MessageProtocol) -> bool:
        """Validate that this agent is allowed to send the given message type."""
        return type(message) in self.sending_messages
