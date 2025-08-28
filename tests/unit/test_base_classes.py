"""Tests for BaseMessage and BaseAgent contracts."""

import pytest
from typing import Callable, Dict
from agent_communication.base import BaseMessage, BaseAgent


class TestBaseMessage:
    """Test the BaseMessage contract."""

    def test_message_must_implement_get_channel_pattern(self) -> None:
        """Test that concrete message classes must implement get_channel_pattern."""

        # Pydantic v2 enforces abstract methods - can't instantiate without implementing them
        with pytest.raises(TypeError) as exc_info:

            class InvalidMessage(BaseMessage):
                data: str

            InvalidMessage(data="test")  # type: ignore[abstract]

        assert "get_channel_pattern" in str(exc_info.value)

    def test_message_with_channel_pattern_instantiates(self) -> None:
        """Test that a properly implemented message class can be instantiated."""

        class ValidMessage(BaseMessage):
            data: str
            value: int

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        # Should be able to instantiate
        message = ValidMessage(data="test", value=42)
        assert message.data == "test"
        assert message.value == 42

        # Should be able to get channel pattern
        pattern_func = message.get_channel_pattern()
        assert pattern_func("request", "abc") == "ValidMessage:request:abc"

    def test_message_inherits_pydantic_validation(self) -> None:
        """Test that messages have Pydantic validation."""

        class TypedMessage(BaseMessage):
            count: int
            name: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        # Valid data should work
        message = TypedMessage(count=10, name="test")
        assert message.count == 10

        # Invalid data should raise validation error
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TypedMessage(count="not_a_number", name="test")  # type: ignore[arg-type]


class TestBaseAgent:
    """Test the BaseAgent contract."""

    def test_agent_must_implement_handle_message(self) -> None:
        """Test that concrete agents must implement handle_message."""

        # This should fail because handle_message is not implemented
        with pytest.raises(TypeError):

            class InvalidAgent(BaseAgent):
                pass

            InvalidAgent()  # type: ignore[abstract]

    def test_agent_message_declarations(self) -> None:
        """Test that agents can declare incoming and outgoing message types."""

        class RequestMessage(BaseMessage):
            data: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        class ResponseMessage(BaseMessage):
            result: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        class TestAgent(BaseAgent):
            messages = [RequestMessage]
            sending_messages = [ResponseMessage]

            def handle_message(
                self, message: BaseMessage, context: Dict[str, str]
            ) -> None:
                pass

        agent = TestAgent()
        assert RequestMessage in agent.messages
        assert ResponseMessage in agent.sending_messages

    def test_agent_validate_incoming_message(self) -> None:
        """Test that agents can validate incoming message types."""

        class AllowedMessage(BaseMessage):
            data: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        class NotAllowedMessage(BaseMessage):
            data: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        class TestAgent(BaseAgent):
            messages = [AllowedMessage]
            sending_messages = []

            def handle_message(
                self, message: BaseMessage, context: Dict[str, str]
            ) -> None:
                pass

        agent = TestAgent()

        allowed_msg = AllowedMessage(data="test")
        not_allowed_msg = NotAllowedMessage(data="test")

        assert agent.validate_incoming_message(allowed_msg) is True
        assert agent.validate_incoming_message(not_allowed_msg) is False

    def test_agent_validate_outgoing_message(self) -> None:
        """Test that agents can validate outgoing message types."""

        class AllowedResponse(BaseMessage):
            result: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        class NotAllowedResponse(BaseMessage):
            result: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        class TestAgent(BaseAgent):
            messages = []
            sending_messages = [AllowedResponse]

            def handle_message(
                self, message: BaseMessage, context: Dict[str, str]
            ) -> None:
                pass

        agent = TestAgent()

        allowed_msg = AllowedResponse(result="success")
        not_allowed_msg = NotAllowedResponse(result="fail")

        assert agent.validate_outgoing_message(allowed_msg) is True
        assert agent.validate_outgoing_message(not_allowed_msg) is False

    def test_agent_handle_message_receives_context(self) -> None:
        """Test that handle_message receives message and context."""

        class TestMessage(BaseMessage):
            data: str

            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"

                return pattern_func

        # Track what was passed to handle_message
        received_message = None
        received_context = None

        class TestAgent(BaseAgent):
            messages = [TestMessage]
            sending_messages = []

            def handle_message(
                self, message: BaseMessage, context: Dict[str, str]
            ) -> None:
                nonlocal received_message, received_context
                received_message = message
                received_context = context

        agent = TestAgent()
        message = TestMessage(data="test_data")
        context = {"session_id": "abc123", "direction": "request"}

        agent.handle_message(message, context)

        assert received_message == message
        assert received_context == context
        assert received_message.data == "test_data"  # type: ignore[attr-defined]
        assert received_context["session_id"] == "abc123"
