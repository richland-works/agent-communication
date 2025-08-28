"""Utility functions for the agent communication package."""

from typing import Dict
from agent_communication.exceptions import InvalidChannelFormat


def parse_channel(channel_name: str) -> Dict[str, str]:
    """Parse a channel name into its components.

    Args:
        channel_name: Channel name in format "MessageClass:direction:session_id"

    Returns:
        Dict with keys: message_class, direction, session_id

    Raises:
        InvalidChannelFormat: If channel name doesn't match expected format
    """
    parts = channel_name.split(":")

    if len(parts) != 3:
        raise InvalidChannelFormat(channel_name, "MessageClass:direction:session_id")

    return {
        "message_class": parts[0],
        "direction": parts[1],
        "session_id": parts[2],
    }
