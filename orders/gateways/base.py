"""Payment gateway abstractions.

Each gateway (eSewa, Khalti, FonePay, …) implements ``PaymentGateway`` and
is registered in ``orders.gateways.registry``.  The checkout flows call the
registry by ``PaymentMethod`` label so the storefront and the API share the
same integration.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class TransactionResult:
    """What a gateway returns after initiating or verifying a payment."""

    ok: bool
    transaction_id: Optional[str] = None
    amount: Optional[int] = None  # paisa / smallest currency unit
    status: Optional[str] = None
    raw: Optional[Dict] = None
    error: Optional[str] = None


class PaymentGateway(ABC):
    """Abstract payment gateway.

    Implementations talk to a specific provider (eSewa, Khalti, …).
    """

    label: str = ""  # matches Order.PaymentMethod value, e.g. "ESEWA"

    @abstractmethod
    def initiate(self, order, base_url: str) -> str:
        """Return the URL to redirect the customer to for payment."""

    @abstractmethod
    def verify(self, params: Dict[str, str]) -> TransactionResult:
        """Verify a callback / redirect from the provider.

        ``params`` are the query-string or form POST values eSewa/provider
        sends back.  Returns a ``TransactionResult``.
        """

    def webhook(self, body: Dict, signature: Optional[str] = None) -> TransactionResult:
        """Optional: handle a server-to-server webhook notification.

        The default implementation delegates to ``verify``.  Override for
        providers that send a signed webhook body different from the redirect
        callback.
        """
        return self.verify(body)
