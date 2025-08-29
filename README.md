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

## Production Architecture

### Understanding the Stack

The `agent-communication` package is designed as a **foundational messaging library** - think of it like Flask for web applications or SQLAlchemy for databases. It provides the core primitives for reliable agent-based messaging, but production systems require additional layers for resilience, performance, and game-specific logic.

### Architectural Layers

```
┌─────────────────────────────────────┐
│     Game-Specific Layer            │ ← Your game logic
│  (game rules, state, mechanics)     │
├─────────────────────────────────────┤
│    Performance Layer (Optional)     │ ← Caching, batching
│  (optimization, compression)        │
├─────────────────────────────────────┤
│     Resilience Layer (Optional)     │ ← Persistence, replay
│  (journaling, transactions)         │
├─────────────────────────────────────┤
│    agent-communication (Core)       │ ← This package
│  (routing, pub/sub, patterns)       │
├─────────────────────────────────────┤
│     Infrastructure (Redis/RMQ)      │ ← Message brokers
└─────────────────────────────────────┘
```

### What This Package Provides

**Core Messaging Features** ✅
- Type-safe message definitions with Pydantic
- Agent abstraction with subscription management
- Redis and RabbitMQ router implementations
- Pattern-based message routing
- Automatic reconnection and basic resilience
- Message serialization/deserialization
- Comprehensive logging

**Basic Production Features** ✅
- Durable queues (RabbitMQ)
- Message persistence
- Connection pooling
- Health checks
- Graceful shutdown

### What You Need to Add for Production

#### 1. Resilience Layer (Preventing Data Loss)

For production games where losing player progress is unacceptable, add a resilience layer:

```python
# Example: Message journaling wrapper
from agent_communication import RedisRouter
from your_resilience_package import MessageJournal, CircuitBreaker

# Base router from this package
base_router = RedisRouter(url="redis://localhost")

# Add journaling for persistence
journaled_router = MessageJournal(
    router=base_router,
    journal_path="/var/log/messages",
    checkpoint_interval=100
)

# Add circuit breaker for fault tolerance
protected_router = CircuitBreaker(
    router=journaled_router,
    failure_threshold=5,
    recovery_timeout=30
)
```

**Features to implement:**
- Write-ahead logging
- Message replay from checkpoints
- Distributed transactions
- Saga pattern for complex workflows
- Dead letter queue handling

#### 2. Performance Layer (Achieving Low Latency)

For games requiring <50ms latency with thousands of concurrent players:

```python
# Example: Performance optimization wrapper
from agent_communication import RabbitMQRouter
from your_performance_package import BatchingRouter, MessageCache

# Base router from this package
base_router = RabbitMQRouter(url="amqp://localhost")

# Add batching for throughput
batched_router = BatchingRouter(
    router=base_router,
    batch_size=100,
    batch_timeout=0.01  # 10ms
)

# Add caching for frequently accessed data
cached_router = MessageCache(
    router=batched_router,
    cache_ttl=60,
    cache_size=10000
)
```

**Features to implement:**
- Message batching and compression
- Local caching with Redis/Memcached
- Connection multiplexing
- Priority queues
- Geographic routing

#### 3. Security Layer (For Public Games)

For games exposed to the internet:

```python
# Example: Security wrapper
from agent_communication import RedisRouter
from your_security_package import SecureRouter, RateLimiter

base_router = RedisRouter(url="redis://localhost")

# Add authentication and rate limiting
secure_router = SecureRouter(
    router=base_router,
    auth_provider=YourAuthProvider(),
    rate_limiter=RateLimiter(
        max_per_second=100,
        max_burst=500
    ),
    encryption_key=YOUR_KEY
)
```

**Features to implement:**
- Message authentication
- Rate limiting per player
- Message encryption
- Input validation and sanitization
- Access control lists

### Complete Production Example

Here's how to compose all layers for a production game:

```python
from agent_communication import RedisRouter, BaseAgent, BaseMessage
from resilience import MessageJournal, CircuitBreaker
from performance import BatchingRouter, CompressingRouter
from security import AuthenticatedRouter, RateLimiter
from your_game import GameStateManager, PlayerAgent

# 1. Start with core messaging
core_router = RedisRouter(
    url="redis://redis-cluster:6379",
    connection_pool_size=50
)

# 2. Add resilience
resilient_router = CircuitBreaker(
    MessageJournal(core_router, journal_dir="/data/journal"),
    failure_threshold=5,
    recovery_timeout=30
)

# 3. Add performance
fast_router = BatchingRouter(
    CompressingRouter(resilient_router, algorithm="lz4"),
    batch_size=100,
    batch_timeout=0.005  # 5ms
)

# 4. Add security
secure_router = AuthenticatedRouter(
    RateLimiter(fast_router, max_rps=1000),
    auth_service=YourAuthService()
)

# 5. Initialize your game
game = GameStateManager(router=secure_router)
player_agent = PlayerAgent(router=secure_router)

# Ready for production!
await game.start()
```

### Testing Strategy for Production

Each layer should be tested independently:

```python
# Test core messaging (this package)
pytest tests/unit tests/integration

# Test resilience layer
pytest your_resilience_package/tests --marks="failover"

# Test performance layer
pytest your_performance_package/tests --marks="load"

# Test security layer
pytest your_security_package/tests --marks="security"

# Test complete stack
pytest your_game/tests/e2e --marks="production"
```

### Infrastructure Considerations

For production deployment:

**Redis Setup:**
- Use Redis Sentinel or Redis Cluster for HA
- Enable persistence (AOF or RDB)
- Configure appropriate memory policies
- Set up monitoring with Redis Exporter

**RabbitMQ Setup:**
- Use RabbitMQ clustering with mirrored queues
- Configure dead letter exchanges
- Set up management plugin for monitoring
- Use durable queues and persistent messages

**Network:**
- Use private networks between services
- Configure firewalls and security groups
- Consider service mesh (Istio, Linkerd)
- Set up load balancers for broker access

### When to Use What

**Use agent-communication alone when:**
- Building prototypes or MVPs
- Testing game mechanics locally
- Learning the system
- Building non-critical internal tools

**Add resilience layer when:**
- Player progress must never be lost
- System needs to recover from failures
- Distributed transactions are required
- Audit trail is necessary

**Add performance layer when:**
- Serving >1000 concurrent players
- Latency requirements <50ms
- High message throughput (>10k msg/sec)
- Geographic distribution needed

**Add security layer when:**
- Game is publicly accessible
- Real money or valuable items involved
- Competitive gameplay (anti-cheat)
- Regulatory compliance required

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

### Phase 2 (v0.2.0) ✅ Complete
- [x] Redis backend implementation with pub/sub
- [x] RabbitMQ backend with topic exchanges
- [x] Message serialization/deserialization
- [x] Auto-subscription based on agent declarations
- [x] Pattern matching with wildcards
- [x] Connection pooling and health checks
- [x] Graceful shutdown and cleanup
- [x] Comprehensive integration tests

### Phase 3 (v0.3.0) - Planned
- [ ] Connection retry with exponential backoff
- [ ] Batch message publishing API
- [ ] Metrics hooks for monitoring
- [ ] Protocol buffers support
- [ ] Better error recovery mechanisms
- [ ] Performance benchmarks

### Out of Scope (Use Additional Layers)
These features are intentionally NOT part of this package to maintain focus and composability:
- ❌ Message journaling/replay (use resilience layer)
- ❌ Rate limiting (use security layer)
- ❌ Message compression (use performance layer)
- ❌ Authentication/authorization (use security layer)
- ❌ Distributed transactions (use resilience layer)
- ❌ Load balancing (use infrastructure layer)
- ❌ Game-specific logic (implement in your game)

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
