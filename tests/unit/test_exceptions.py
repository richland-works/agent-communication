"""Tests for custom exception classes and error messages."""

import pytest
from agent_communication.exceptions import (
    AgentCommunicationError,
    InvalidChannelFormat,
    MessageClassNotRegistered,
    MessageValidationError,
    InvalidAgentError,
    NoAgentFoundError,
)


class TestExceptions:
    """Test custom exception classes provide helpful error messages."""
    
    def test_base_exception_inherits_from_exception(self):
        """Test that AgentCommunicationError is a proper exception."""
        error = AgentCommunicationError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_invalid_channel_format_message(self):
        """Test InvalidChannelFormat provides helpful error message."""
        error = InvalidChannelFormat("bad_channel")
        
        assert "bad_channel" in str(error)
        assert "invalid format" in str(error)
        assert "Expected: 'MessageClass:direction:session_id'" in str(error)
        assert error.channel == "bad_channel"
        assert error.expected_format == "MessageClass:direction:session_id"
    
    def test_invalid_channel_format_custom_format(self):
        """Test InvalidChannelFormat with custom expected format."""
        error = InvalidChannelFormat(
            "wrong_format",
            expected_format="Type:SubType:ID"
        )
        
        assert "wrong_format" in str(error)
        assert "Expected: 'Type:SubType:ID'" in str(error)
        assert error.expected_format == "Type:SubType:ID"
    
    def test_message_class_not_registered_without_suggestions(self):
        """Test MessageClassNotRegistered without available classes."""
        error = MessageClassNotRegistered("UnknownMessage")
        
        assert "UnknownMessage" in str(error)
        assert "not found in registry" in str(error)
        assert "Did you forget to register" in str(error)
        assert error.class_name == "UnknownMessage"
        assert error.available_classes == []
    
    def test_message_class_not_registered_with_suggestions(self):
        """Test MessageClassNotRegistered with available classes list."""
        available = ["PaymentMessage", "OrderMessage", "UserMessage"]
        error = MessageClassNotRegistered("UnknownMessage", available)
        
        assert "UnknownMessage" in str(error)
        assert "Available classes: PaymentMessage, OrderMessage, UserMessage" in str(error)
        assert "Did you forget to register" in str(error)
        assert error.available_classes == available
    
    def test_message_validation_error_basic(self):
        """Test MessageValidationError with basic information."""
        error = MessageValidationError(
            "PaymentMessage",
            "amount must be positive"
        )
        
        assert "PaymentMessage" in str(error)
        assert "Failed to deserialize" in str(error)
        assert "amount must be positive" in str(error)
        assert error.class_name == "PaymentMessage"
        assert error.validation_error == "amount must be positive"
        assert error.payload_preview is None
    
    def test_message_validation_error_with_payload(self):
        """Test MessageValidationError with payload preview."""
        payload = '{"amount": -100, "user_id": "123", "metadata": {...}}'
        error = MessageValidationError(
            "PaymentMessage",
            "amount must be positive",
            payload[:50]  # Truncated preview
        )
        
        assert "PaymentMessage" in str(error)
        assert "amount must be positive" in str(error)
        assert "Payload was:" in str(error)
        assert '{"amount": -100' in str(error)
        assert error.payload_preview == payload[:50]
    
    def test_invalid_agent_error(self):
        """Test InvalidAgentError provides helpful guidance."""
        error = InvalidAgentError(
            "AudioAgent",
            "messages",
            "Add: messages = [MessageType1, MessageType2, ...]"
        )
        
        assert "AudioAgent" in str(error)
        assert "missing 'messages' attribute" in str(error)
        assert "Add: messages = [MessageType1, MessageType2, ...]" in str(error)
        assert error.agent_class == "AudioAgent"
        assert error.missing_attribute == "messages"
        assert error.suggestion == "Add: messages = [MessageType1, MessageType2, ...]"
    
    def test_no_agent_found_error(self):
        """Test NoAgentFoundError provides helpful message."""
        error = NoAgentFoundError("AudioRequestMessage")
        
        assert "AudioRequestMessage" in str(error)
        assert "No agent registered to handle" in str(error)
        assert "Register an agent with this message type" in str(error)
        assert "in its 'messages' list" in str(error)
        assert error.message_type == "AudioRequestMessage"
    
    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from AgentCommunicationError."""
        exceptions = [
            InvalidChannelFormat("test"),
            MessageClassNotRegistered("test"),
            MessageValidationError("test", "error"),
            InvalidAgentError("test", "attr", "suggestion"),
            NoAgentFoundError("test"),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, AgentCommunicationError)
            assert isinstance(exc, Exception)