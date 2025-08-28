import pytest
from typing import Type, Callable
from pydantic import BaseModel


class TestMessageRouting:
    """Test message classes generate correct channel patterns."""
    
    def test_message_channel_pattern_generation(self):
        """Test that message classes can generate correct channel patterns."""
        from agent_communication.base import BaseMessage
        
        class TestRequestMessage(BaseMessage):
            data: str
            
            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"
                return pattern_func
        
        message = TestRequestMessage(data="test")
        channel_func = message.get_channel_pattern()
        channel = channel_func(direction="request", session_id="abc123")
        
        assert channel == "TestRequestMessage:request:abc123"
    
    def test_message_channel_pattern_with_different_directions(self):
        """Test channel patterns work with different directions."""
        from agent_communication.base import BaseMessage
        
        class AudioMessage(BaseMessage):
            file_path: str
            
            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"
                return pattern_func
        
        message = AudioMessage(file_path="/test/audio.mp3")
        channel_func = message.get_channel_pattern()
        
        assert channel_func(direction="request", session_id="123") == "AudioMessage:request:123"
        assert channel_func(direction="response", session_id="123") == "AudioMessage:response:123"
    
    def test_parse_channel_extracts_components(self):
        """Test parsing channel name extracts message class, direction, and session_id."""
        from agent_communication.utils import parse_channel
        
        channel = "PaymentRequestMessage:request:session456"
        parsed = parse_channel(channel)
        
        assert parsed["message_class"] == "PaymentRequestMessage"
        assert parsed["direction"] == "request"
        assert parsed["session_id"] == "session456"
    
    def test_parse_channel_handles_invalid_format(self):
        """Test parsing channel raises helpful error for invalid format."""
        from agent_communication.utils import parse_channel
        from agent_communication.exceptions import InvalidChannelFormat
        
        with pytest.raises(InvalidChannelFormat) as exc_info:
            parse_channel("invalid_channel")
        
        assert "invalid_channel" in str(exc_info.value)
        assert "Expected: 'MessageClass:direction:session_id'" in str(exc_info.value)
    
    def test_multiple_message_types_have_unique_patterns(self):
        """Test different message types generate unique channel patterns."""
        from agent_communication.base import BaseMessage
        
        class PaymentRequestMessage(BaseMessage):
            amount: float
            
            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"
                return pattern_func
        
        class PaymentResponseMessage(BaseMessage):
            success: bool
            
            @classmethod
            def get_channel_pattern(cls) -> Callable[[str, str], str]:
                def pattern_func(direction: str, session_id: str) -> str:
                    return f"{cls.__name__}:{direction}:{session_id}"
                return pattern_func
        
        req_msg = PaymentRequestMessage(amount=100.0)
        resp_msg = PaymentResponseMessage(success=True)
        
        req_channel = req_msg.get_channel_pattern()(direction="request", session_id="abc")
        resp_channel = resp_msg.get_channel_pattern()(direction="response", session_id="abc")
        
        assert req_channel == "PaymentRequestMessage:request:abc"
        assert resp_channel == "PaymentResponseMessage:response:abc"
        assert req_channel != resp_channel