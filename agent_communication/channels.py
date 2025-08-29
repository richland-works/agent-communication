"""Channel management utilities for agent communication."""

from typing import Dict, List, Optional
import re


class ChannelManager:
    """Utility class for managing channel patterns and routing."""

    @staticmethod
    def create_channel(
        message_class: str, direction: str = "request", session_id: str = "*"
    ) -> str:
        """Create a channel name from components.

        Args:
            message_class: Name of the message class
            direction: Direction (request/response)
            session_id: Session identifier or wildcard

        Returns:
            Formatted channel name
        """
        return f"{message_class}:{direction}:{session_id}"

    @staticmethod
    def parse_channel(channel: str) -> Dict[str, str]:
        """Parse a channel name into its components.

        Args:
            channel: Channel name to parse

        Returns:
            Dictionary with message_class, direction, and session_id

        Raises:
            ValueError: If channel format is invalid
        """
        parts = channel.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid channel format: {channel}. "
                f"Expected: 'MessageClass:direction:session_id'"
            )

        return {
            "message_class": parts[0],
            "direction": parts[1],
            "session_id": parts[2],
        }

    @staticmethod
    def match_pattern(channel: str, pattern: str) -> bool:
        """Check if a channel matches a pattern.

        Supports wildcards:
        - * matches any single segment
        - ** matches any number of segments

        Args:
            channel: Channel name to check
            pattern: Pattern to match against

        Returns:
            True if channel matches pattern
        """
        if pattern == channel:
            return True

        pattern_regex = pattern.replace("**", ".*")
        pattern_regex = pattern_regex.replace("*", "[^:]*")
        pattern_regex = f"^{pattern_regex}$"

        return bool(re.match(pattern_regex, channel))

    @staticmethod
    def extract_session_id(channel: str) -> Optional[str]:
        """Extract session ID from a channel name.

        Args:
            channel: Channel name

        Returns:
            Session ID or None if not found
        """
        try:
            components = ChannelManager.parse_channel(channel)
            session_id = components.get("session_id")
            return session_id if session_id != "*" else None
        except ValueError:
            return None

    @staticmethod
    def create_response_channel(request_channel: str) -> str:
        """Create a response channel from a request channel.

        Args:
            request_channel: Request channel name

        Returns:
            Corresponding response channel name
        """
        components = ChannelManager.parse_channel(request_channel)
        components["direction"] = "response"
        return ChannelManager.create_channel(
            components["message_class"],
            components["direction"],
            components["session_id"],
        )

    @staticmethod
    def create_broadcast_pattern(message_class: str) -> str:
        """Create a pattern for broadcasting to all instances of a message type.

        Args:
            message_class: Name of the message class

        Returns:
            Broadcast pattern
        """
        return f"{message_class}:*:*"

    @staticmethod
    def create_session_pattern(session_id: str) -> str:
        """Create a pattern for all messages in a session.

        Args:
            session_id: Session identifier

        Returns:
            Session pattern
        """
        return f"*:*:{session_id}"

    @staticmethod
    def validate_channel_name(channel: str) -> bool:
        """Validate that a channel name is well-formed.

        Args:
            channel: Channel name to validate

        Returns:
            True if channel name is valid
        """
        try:
            ChannelManager.parse_channel(channel)
            return True
        except ValueError:
            return False


class ChannelRouter:
    """Advanced routing logic for channel-based messaging."""

    def __init__(self) -> None:
        """Initialize the channel router."""
        self._routes: Dict[str, List[str]] = {}

    def add_route(self, source_pattern: str, target_patterns: List[str]) -> None:
        """Add a routing rule.

        Args:
            source_pattern: Source channel pattern
            target_patterns: List of target channel patterns
        """
        if source_pattern not in self._routes:
            self._routes[source_pattern] = []
        self._routes[source_pattern].extend(target_patterns)

    def get_routes(self, channel: str) -> List[str]:
        """Get all target patterns for a channel.

        Args:
            channel: Channel to route from

        Returns:
            List of target patterns
        """
        targets = []
        for pattern, target_patterns in self._routes.items():
            if ChannelManager.match_pattern(channel, pattern):
                targets.extend(target_patterns)
        return list(set(targets))

    def clear_routes(self) -> None:
        """Clear all routing rules."""
        self._routes.clear()
