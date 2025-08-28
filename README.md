# Agent Communication

A Python package for reliable, typed inter-agent messaging with support for multiple backends (Redis, RabbitMQ). Built with type safety, comprehensive logging, and developer-friendly error messages.

## Features

- 🚀 **Type-Safe Messaging**: Full Pydantic validation and mypy support
- 📝 **Structured Logging**: JSON Lines format with comprehensive context
- 🔌 **Multiple Backends**: Redis and RabbitMQ support (coming in v0.2)
- 🎯 **Smart Routing**: Message classes define their own routing patterns
- 🛡️ **Developer-Friendly**: Helpful error messages that guide you
- ✅ **Well-Tested**: Comprehensive test coverage with TDD approach

## Installation

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/agent-communication.git
cd agent-communication

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/yourusername/agent-communication.git
cd agent-communication

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

## Quick Start

### 1. Define Your Messages

```python
from typing import Callable
from agent_communication.base import BaseMessage

class PaymentRequestMessage(BaseMessage):
    """Message for payment processing requests."""
    
    amount: float
    user_id: str
    payment_method: str
    
    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"
        return pattern_func

class PaymentResponseMessage(BaseMessage):
    """Message for payment processing responses."""
    
    success: bool
    transaction_id: str
    message: str
    
    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"
        return pattern_func
```

### 2. Create Your Agent

```python
from typing import Dict
from agent_communication.base import BaseAgent, BaseMessage
from agent_communication.logger import get_logger

class PaymentAgent(BaseAgent):
    """Agent that handles payment processing."""
    
    # Declare message types this agent can receive
    messages = [PaymentRequestMessage]
    
    # Declare message types this agent can send
    sending_messages = [PaymentResponseMessage]
    
    def __init__(self):
        self.logger = get_logger("PaymentAgent")
    
    def handle_message(self, message: BaseMessage, context: Dict[str, str]) -> None:
        """Process incoming payment requests."""
        if isinstance(message, PaymentRequestMessage):
            self.logger.info(
                "Processing payment",
                extra={
                    "amount": message.amount,
                    "user_id": message.user_id,
                    "session_id": context.get("session_id")
                }
            )
            
            # Process the payment...
            
            # Create response
            response = PaymentResponseMessage(
                success=True,
                transaction_id="TXN123456",
                message=f"Payment of ${message.amount} processed successfully"
            )
            
            # Validate we can send this message type
            assert self.validate_outgoing_message(response)
```

### 3. Use Channel Patterns

```python
from agent_communication.utils import parse_channel

# Generate channel name for routing
msg = PaymentRequestMessage(
    amount=100.0,
    user_id="user123",
    payment_method="credit_card"
)

channel = msg.get_channel_pattern()(
    direction="request",
    session_id="session456"
)
# Result: "PaymentRequestMessage:request:session456"

# Parse channel to extract components
parsed = parse_channel(channel)
print(parsed)
# {'message_class': 'PaymentRequestMessage', 'direction': 'request', 'session_id': 'session456'}
```

## Structured Logging

The package includes JSON Lines logging for observability:

```python
from agent_communication.logger import get_logger

logger = get_logger("MyAgent")

logger.info("Processing message", extra={
    "agent_id": "agent_1",
    "message_type": "PaymentRequest",
    "session_id": "abc123"
})
```

Output:
```json
{"timestamp": "2024-08-27T15:30:45.123Z", "level": "INFO", "message": "Processing message", "file": "my_agent.py", "line": 45, "agent_id": "agent_1", "message_type": "PaymentRequest", "session_id": "abc123"}
```

## Exception Handling

The package provides developer-friendly exceptions:

```python
from agent_communication.exceptions import (
    InvalidChannelFormat,
    MessageClassNotRegistered,
    NoAgentFoundError
)

# Clear error messages guide you to the solution
try:
    parse_channel("invalid_format")
except InvalidChannelFormat as e:
    print(e)
    # Channel 'invalid_format' has invalid format. 
    # Expected: 'MessageClass:direction:session_id', got: 'invalid_format'
```

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=agent_communication

# Run specific test file
poetry run pytest tests/unit/test_base_classes.py -v
```

### Type Checking

```bash
# Run mypy type checking
poetry run mypy agent_communication --strict
```

### Code Style

```bash
# Format code with black (add to dev dependencies first)
poetry add --group dev black
poetry run black agent_communication tests

# Lint with flake8 (add to dev dependencies first)
poetry add --group dev flake8
poetry run flake8 agent_communication tests
```

## Project Structure

```
agent-communication/
├── agent_communication/
│   ├── __init__.py           # Package exports
│   ├── base.py               # BaseAgent and BaseMessage classes
│   ├── exceptions.py         # Custom exceptions
│   ├── logger.py             # JSON Lines logging
│   └── utils.py              # Utility functions
├── tests/
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests (coming soon)
│   └── examples/             # Example implementations
├── .env.example              # Environment configuration template
├── .gitignore               # Git ignore rules
├── pyproject.toml           # Poetry configuration
└── README.md                # This file
```

## Configuration

Copy `.env.example` to `.env` and configure as needed:

```bash
cp .env.example .env
```

Key configuration options:
- `MESSAGING_BACKEND`: Choose between `redis` or `rabbitmq`
- `LOG_LEVEL`: Set logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `REDIS_URL` / `RABBITMQ_URL`: Backend connection strings

## API Reference

### BaseMessage

Abstract base class for all messages. Subclasses must implement:
- `get_channel_pattern()`: Returns a function that generates channel patterns

### BaseAgent

Abstract base class for all agents. Subclasses must:
- Define `messages`: List of message types the agent can receive
- Define `sending_messages`: List of message types the agent can send
- Implement `handle_message()`: Process incoming messages

### Exceptions

- `AgentCommunicationError`: Base exception for all package errors
- `InvalidChannelFormat`: Raised when channel format is invalid
- `MessageClassNotRegistered`: Raised when message class isn't found
- `NoAgentFoundError`: Raised when no agent handles a message type
- `InvalidAgentError`: Raised when agent doesn't meet requirements

## Roadmap

### Phase 1 (v0.1.0) ✅ Complete
- [x] Core abstractions (BaseMessage, BaseAgent)
- [x] Channel pattern routing
- [x] JSON Lines logging
- [x] Custom exceptions
- [x] Type safety with mypy
- [x] Comprehensive test suite

### Phase 2 (v0.2.0) - In Progress
- [ ] Redis backend implementation
- [ ] RabbitMQ backend implementation
- [ ] MessagingSystem orchestrator
- [ ] Auto-subscription based on agent declarations
- [ ] Message serialization/deserialization

### Phase 3 (v0.3.0) - Planned
- [ ] Performance optimizations
- [ ] Message middleware support
- [ ] Metrics and monitoring
- [ ] Circuit breaker patterns
- [ ] Message replay capabilities

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Implement your changes
5. Run tests and type checking
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Acknowledgments

This package emerged from lessons learned building distributed systems where consistent message routing and type safety were critical for reliability.