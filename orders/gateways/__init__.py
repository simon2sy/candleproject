"""Payment gateway registry.

Look a gateway up by ``Order.PaymentMethod`` label::

    from orders.gateways import get_gateway, gateway_ready

    gw = get_gateway(order.payment_method)
    if gateway_ready(gw):
        pay_url = gw.initiate(order, callback_url)

Gateways without credentials (or not implemented yet) return ``None`` /
``False`` so callers can fall back to the manual WhatsApp verification flow.
"""
from __future__ import annotations

import logging
from typing import Optional

from orders.gateways.base import PaymentGateway, TransactionResult

logger = logging.getLogger(__name__)

# The eSewa gateway needs the optional ``requests`` dependency.  If it is
# missing (or the module is broken) the gateway is simply disabled and the
# store keeps running on the manual WhatsApp payment flow — an optional
# payment integration must never crash the whole storefront.
try:
    from orders.gateways.esewa import EsewaGateway
except ImportError as exc:  # pragma: no cover - environment-dependent
    EsewaGateway = None  # type: ignore[assignment]
    logger.warning("eSewa gateway disabled (optional dependency missing): %s", exc)

_REGISTRY = {}
if EsewaGateway is not None:
    _REGISTRY["ESEWA"] = EsewaGateway
# Add Khalti/FonePay here when their gateway modules exist:
# _REGISTRY["KHALTI"] = KhaltiGateway


def get_gateway(label: str) -> Optional[PaymentGateway]:
    """Return a fresh gateway instance for ``label``, or ``None`` if unknown."""
    cls = _REGISTRY.get((label or "").strip().upper())
    return cls() if cls else None


def gateway_ready(gateway: Optional[PaymentGateway]) -> bool:
    """True when the gateway has its required credentials configured."""
    if gateway is None:
        return False
    merchant = getattr(gateway, "merchant_id", None)
    secret = getattr(gateway, "secret_key", None)
    if merchant is not None or secret is not None:
        return bool(merchant and secret)
    # Gateways without a merchant/secret shape (e.g. COD-style) count as ready.
    return True


__all__ = ["PaymentGateway", "TransactionResult", "get_gateway", "gateway_ready"]
