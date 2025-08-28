"""Tests for JSON logging functionality."""

import json
import logging
import pytest
from datetime import datetime, timezone
from io import StringIO


class TestJSONLineFormatter:
    """Test the JSON Lines formatter for logging."""
    
    def test_format_creates_valid_json_line(self):
        """Test that the formatter creates valid JSON output."""
        from agent_communication.logger import JSONLineFormatter
        
        formatter = JSONLineFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Should be valid JSON
        parsed = json.loads(formatted)
        assert isinstance(parsed, dict)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert parsed["file"] == "file.py"
        assert parsed["line"] == 42
    
    def test_format_includes_all_required_fields(self):
        """Test that formatted output includes all required fields."""
        from agent_communication.logger import JSONLineFormatter
        
        formatter = JSONLineFormatter()
        
        record = logging.LogRecord(
            name="agent_messaging.test",
            level=logging.ERROR,
            pathname="/path/to/module.py",
            lineno=123,
            msg="Error occurred",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Check all required fields are present
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed
        assert "file" in parsed
        assert "line" in parsed
        
        # Check values
        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error occurred"
        assert parsed["file"] == "module.py"
        assert parsed["line"] == 123
    
    def test_timestamp_format_iso_with_z(self):
        """Test that timestamp is in ISO format with Z suffix."""
        from agent_communication.logger import JSONLineFormatter
        
        formatter = JSONLineFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        timestamp = parsed["timestamp"]
        assert timestamp.endswith("Z")
        
        # Should be parseable as ISO format
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt.tzinfo is not None
    
    def test_extra_fields_included_in_output(self):
        """Test that extra fields from LogRecord are included in JSON."""
        from agent_communication.logger import JSONLineFormatter
        
        formatter = JSONLineFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Processing message",
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.agent_id = "audio_1"
        record.message_type = "AudioRequestMessage"
        record.session_id = "abc123"
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed["agent_id"] == "audio_1"
        assert parsed["message_type"] == "AudioRequestMessage"
        assert parsed["session_id"] == "abc123"
    
    def test_get_logger_returns_configured_logger(self):
        """Test that get_logger returns a properly configured logger."""
        from agent_communication.logger import get_logger, JSONLineFormatter
        
        # Create a string buffer to capture log output
        buffer = StringIO()
        
        logger = get_logger("TestAgent")
        
        # Clear existing handlers and add our test handler
        logger.handlers.clear()
        handler = logging.StreamHandler(buffer)
        handler.setFormatter(JSONLineFormatter())
        logger.addHandler(handler)
        
        # Log a message with extra fields
        logger.info("Test message", extra={
            "agent_id": "test_1",
            "session_id": "xyz789"
        })
        
        # Get the output
        output = buffer.getvalue()
        
        # Should be valid JSON
        parsed = json.loads(output.strip())
        assert parsed["message"] == "Test message"
        assert parsed["agent_id"] == "test_1"
        assert parsed["session_id"] == "xyz789"
    
    def test_multiple_log_lines_are_separate_json_objects(self):
        """Test that multiple log entries create separate JSON objects."""
        from agent_communication.logger import JSONLineFormatter
        
        formatter = JSONLineFormatter()
        buffer = StringIO()
        handler = logging.StreamHandler(buffer)
        handler.setFormatter(formatter)
        
        logger = logging.getLogger("test_multi")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Log multiple messages
        logger.info("First message")
        logger.warning("Second message")
        logger.error("Third message")
        
        # Each line should be valid JSON
        output = buffer.getvalue()
        lines = output.strip().split("\n")
        
        assert len(lines) == 3
        
        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
            assert "timestamp" in parsed
            assert "level" in parsed
            assert "message" in parsed
        
        # Check specific content
        assert json.loads(lines[0])["message"] == "First message"
        assert json.loads(lines[1])["message"] == "Second message"
        assert json.loads(lines[2])["message"] == "Third message"
        assert json.loads(lines[0])["level"] == "INFO"
        assert json.loads(lines[1])["level"] == "WARNING"
        assert json.loads(lines[2])["level"] == "ERROR"