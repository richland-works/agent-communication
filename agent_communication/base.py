"""Base classes for agent messaging system."""

from abc import ABC, abstractmethod
from typing import List, Type, Callable, Dict, Any, Optional
from pydantic import BaseModel


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
    """
    
    messages: List[Type[BaseMessage]] = []
    sending_messages: List[Type[BaseMessage]] = []
    
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