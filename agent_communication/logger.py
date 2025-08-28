"""JSON Lines logging configuration for the agent communication package."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any


class JSONLineFormatter(logging.Formatter):
    """Formatter that outputs log records as JSON Lines."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON line.
        
        Args:
            record: The LogRecord to format
            
        Returns:
            A JSON string (single line) with all log information
        """
        # Create base log entry with required fields
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "file": os.path.basename(record.pathname),
            "line": record.lineno,
        }
        
        # Add any extra fields from the record
        # Skip internal logging fields
        skip_fields = {
            "name", "msg", "args", "created", "msecs", "levelname", "levelno",
            "pathname", "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "processName", "process", "threadName", "thread",
            "getMessage", "relativeCreated", "taskName"
        }
        
        for key, value in record.__dict__.items():
            if key not in skip_fields and not key.startswith("_"):
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """Get a logger configured with JSON Lines formatting.
    
    Args:
        name: The name for the logger (typically the agent or module name)
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(f"agent_messaging.{name}")
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create handler with JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(JSONLineFormatter())
        logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        logger.propagate = False
    
    return logger