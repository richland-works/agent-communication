"""Example usage of the agent communication package for a payment system."""

import pytest
from typing import Callable, Dict
from agent_communication.base import BaseMessage, BaseAgent
from agent_communication.logger import get_logger


class PaymentRequestMessage(BaseMessage):
    """Message requesting payment processing."""

    amount: float
    user_id: str
    payment_method: str

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class PaymentResponseMessage(BaseMessage):
    """Message containing payment result."""

    success: bool
    transaction_id: str
    message: str

    @classmethod
    def get_channel_pattern(cls) -> Callable[[str, str], str]:
        def pattern_func(direction: str, session_id: str) -> str:
            return f"{cls.__name__}:{direction}:{session_id}"

        return pattern_func


class PaymentAgent(BaseAgent):
    """Agent that handles payment processing."""

    messages = [PaymentRequestMessage]
    sending_messages = [PaymentResponseMessage]

    def __init__(self) -> None:
        self.logger = get_logger("PaymentAgent")
        self.processed_payments: list[PaymentRequestMessage] = []

    def handle_message(self, message: BaseMessage, context: Dict[str, str]) -> None:
        """Process incoming payment request."""
        if isinstance(message, PaymentRequestMessage):
            self.logger.info(
                "Processing payment request",
                extra={
                    "amount": message.amount,
                    "user_id": message.user_id,
                    "session_id": context.get("session_id"),
                },
            )

            # Store for testing
            self.processed_payments.append(message)

            # In a real system, would send response here
            response = PaymentResponseMessage(
                success=True,
                transaction_id="TXN123456",
                message=f"Payment of ${message.amount} processed",
            )

            # Validate we can send this message type
            assert self.validate_outgoing_message(response)


class TestPaymentExample:
    """Test the payment processing example."""

    def test_payment_request_channel_pattern(self) -> None:
        """Test that payment request generates correct channel."""
        msg = PaymentRequestMessage(
            amount=100.0, user_id="user123", payment_method="credit_card"
        )

        channel_func = msg.get_channel_pattern()
        channel = channel_func("request", "session789")

        assert channel == "PaymentRequestMessage:request:session789"

    def test_payment_agent_handles_request(self) -> None:
        """Test that PaymentAgent processes payment requests."""
        agent = PaymentAgent()

        # Create a payment request
        request = PaymentRequestMessage(
            amount=50.0, user_id="user456", payment_method="paypal"
        )

        # Process the request
        context = {"session_id": "session123", "direction": "request"}
        agent.handle_message(request, context)

        # Verify it was processed
        assert len(agent.processed_payments) == 1
        assert agent.processed_payments[0].amount == 50.0
        assert agent.processed_payments[0].user_id == "user456"

    def test_payment_agent_validates_messages(self) -> None:
        """Test that PaymentAgent validates incoming and outgoing messages."""
        agent = PaymentAgent()

        # Should accept PaymentRequestMessage
        request = PaymentRequestMessage(
            amount=25.0, user_id="user789", payment_method="debit"
        )
        assert agent.validate_incoming_message(request) is True

        # Should reject PaymentResponseMessage as incoming
        response = PaymentResponseMessage(
            success=True, transaction_id="TXN999", message="Test"
        )
        assert agent.validate_incoming_message(response) is False

        # But should accept PaymentResponseMessage as outgoing
        assert agent.validate_outgoing_message(response) is True
        assert agent.validate_outgoing_message(request) is False

    def test_message_validation(self) -> None:
        """Test Pydantic validation on payment messages."""
        from pydantic import ValidationError

        # Valid message should work
        msg = PaymentRequestMessage(
            amount=100.0, user_id="user123", payment_method="credit"
        )
        assert msg.amount == 100.0

        # Invalid type should fail
        with pytest.raises(ValidationError) as exc_info:
            PaymentRequestMessage(
                amount="not_a_number",  # type: ignore
                user_id="user123",
                payment_method="credit",
            )

        assert "amount" in str(exc_info.value)
