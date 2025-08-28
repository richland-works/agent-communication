"""Custom exceptions with helpful error messages for the agent communication package."""

from typing import List, Optional


class AgentCommunicationError(Exception):
    """Base exception for all agent communication errors."""
    pass


class InvalidChannelFormat(AgentCommunicationError):
    """Raised when a channel name has an invalid format."""
    
    def __init__(self, channel: str, expected_format: str = "MessageClass:direction:session_id"):
        self.channel = channel
        self.expected_format = expected_format
        super().__init__(
            f"Channel '{channel}' has invalid format. "
            f"Expected: '{expected_format}', got: '{channel}'"
        )


class MessageClassNotRegistered(AgentCommunicationError):
    """Raised when trying to deserialize a message class that isn't registered."""
    
    def __init__(self, class_name: str, available_classes: Optional[List[str]] = None):
        self.class_name = class_name
        self.available_classes = available_classes or []
        
        message = f"Message class '{class_name}' not found in registry."
        if self.available_classes:
            message += f" Available classes: {', '.join(self.available_classes)}."
        message += " Did you forget to register an agent that handles this message type?"
        
        super().__init__(message)


class MessageValidationError(AgentCommunicationError):
    """Raised when a message fails Pydantic validation during deserialization."""
    
    def __init__(self, class_name: str, validation_error: str, payload_preview: Optional[str] = None):
        self.class_name = class_name
        self.validation_error = validation_error
        self.payload_preview = payload_preview
        
        message = f"Failed to deserialize {class_name}: {validation_error}."
        if payload_preview:
            message += f" Payload was: {payload_preview}..."
            
        super().__init__(message)


class InvalidAgentError(AgentCommunicationError):
    """Raised when an agent doesn't conform to the required interface."""
    
    def __init__(self, agent_class: str, missing_attribute: str, suggestion: str):
        self.agent_class = agent_class
        self.missing_attribute = missing_attribute
        self.suggestion = suggestion
        
        super().__init__(
            f"Agent {agent_class} missing '{missing_attribute}' attribute. "
            f"{suggestion}"
        )


class NoAgentFoundError(AgentCommunicationError):
    """Raised when no agent is registered to handle a specific message type."""
    
    def __init__(self, message_type: str):
        self.message_type = message_type
        super().__init__(
            f"No agent registered to handle {message_type}. "
            f"Register an agent with this message type in its 'messages' list."
        )