"""eSewa ePay v2 payment gateway (current official API).

Flow (https://developer.esewa.com.np/#ebank):

1. Merchant builds a JSON ``amount`` + ``signature`` (HMAC-SHA256, base64)
   and POSTs ``amount``, ``tax_amount``, ``total_amount``,
   ``transaction_uuid``, ``product_code``, ``product_service_charge``,
   ``product_delivery_charge``, ``success_url``, ``failure_url``,
   ``signed_field_names``, ``signature`` as a form to the ePay v2 endpoint.
2. Customer completes payment on eSewa's page.
3. eSewa redirects (POST) back to ``success_url`` / ``failure_url`` with
   ``transaction_uuid``, ``total_amount``, ``product_code``, ``status``,
   ``signed_field_names`` and ``signature``.
4. Merchant checks the returned signature locally, then double-checks the
   payment by POSTing to the status-check API.  Only ``COMPLETE`` counts.

Environment variables (.env):
    ESEWA_MERCHANT_ID   product code, e.g. EPAYTEST or your live code
    ESEWA_SECRET_KEY    the 8.x secret from eSewa's merchant dashboard
    ESEWA_ENVIRONMENT   "TEST" (default) or "LIVE"
    ESEWA_CALLBACK_URL  optional absolute base; falls back to the URL built
                        from the request at initiate time
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from typing import Dict, Optional

from orders.gateways.base import PaymentGateway, TransactionResult

logger = logging.getLogger("orders.gateways")

# ePay v2 endpoints.  TEST = the public sandbox (EPAYTEST), LIVE = production.
_ENDPOINTS = {
    "TEST": "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
    "LIVE": "https://epay.esewa.com.np/api/epay/main/v2/form",
}
_STATUS_ENDPOINTS = {
    "TEST": "https://rc.esewa.com.np/api/epay/transaction/status/",
    "LIVE": "https://epay.esewa.com.np/api/epay/transaction/status/",
}

SIGNED_FIELD_NAMES = "total_amount,transaction_uuid,product_code"


class EsewaGateway(PaymentGateway):
    """eSewa ePay v2 — form POST redirect with HMAC-SHA256 (base64) signature."""

    label = "ESEWA"

    def __init__(self):
        self.merchant_id = os.getenv("ESEWA_MERCHANT_ID", "").strip()
        self.secret_key = os.getenv("ESEWA_SECRET_KEY", "").strip()
        self.environment = os.getenv("ESEWA_ENVIRONMENT", "TEST").strip().upper()
        self.callback_url = os.getenv("ESEWA_CALLBACK_URL", "").strip()
        if not self.merchant_id:
            logger.warning("eSewa ESEWA_MERCHANT_ID is not set; gateway stays dormant.")

    # ------------------------------------------------------------------
    # signature (per eSewa docs: HMAC-SHA256 over a comma-joined
    # signed_field_names=value string, then base64-encode the digest)
    # ------------------------------------------------------------------

    def _make_signature(self, fields: Dict[str, str]) -> str:
        message = ",".join(
            f"{name}={fields[name]}" for name in SIGNED_FIELD_NAMES.split(",")
        )
        digest = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    @staticmethod
    def _check_signature(fields: Dict[str, str], signature: str, secret: str) -> bool:
        message = ",".join(
            f"{name}={fields[name]}" for name in SIGNED_FIELD_NAMES.split(",")
        )
        digest = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(signature, expected)

    # ------------------------------------------------------------------
    # initiate — build the hidden form POST to eSewa
    # ------------------------------------------------------------------

    def initiate(self, order, base_url: str) -> str:
        """Return the eSewa payment URL.

        ePay v2 expects a browser form POST, so ``initiate`` returns a
        ``javascript:`` URL is *not* acceptable — instead the caller renders
        the returned marker as an auto-submitting form.  For a plain
        redirect-based caller we return the form URL and stash the payload;
        the view uses ``get_initiate_form()`` when it needs the HTML.
        """
        if not self.merchant_id or not self.secret_key:
            raise RuntimeError(
                "eSewa merchant credentials not configured "
                "(ESEWA_MERCHANT_ID / ESEWA_SECRET_KEY)."
            )

        total_amount = f"{order.total:.2f}"  # ePay v2 wants a decimal string
        fields = {
            "total_amount": total_amount,
            "transaction_uuid": order.order_number,
            "product_code": self.merchant_id,
        }
        signature = self._make_signature(fields)

        success_url = self.callback_url or base_url
        if not success_url.endswith("/"):
            success_url += "/"
        success_url += "?action=success" if "?" not in success_url else "&action=success"
        failure_url = success_url.replace("action=success", "action=failure")

        form_fields = {
            "amount": total_amount,
            "tax_amount": "0",
            "total_amount": total_amount,
            "transaction_uuid": order.order_number,
            "product_code": self.merchant_id,
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": success_url,
            "failure_url": failure_url,
            "signed_field_names": SIGNED_FIELD_NAMES,
            "signature": signature,
        }
        self._pending_form_fields = form_fields
        return _ENDPOINTS.get(self.environment, _ENDPOINTS["TEST"])

    def get_initiate_form(self, order, base_url: str) -> str:
        """Full auto-submitting HTML form for ePay v2 (recommended entry)."""
        url = self.initiate(order, base_url)
        fields = getattr(self, "_pending_form_fields", {})
        inputs = "".join(
            f'<input type="hidden" name="{k}" value="{v}"/>' for k, v in fields.items()
        )
        return (
            f'<form id="esewa-form" method="POST" action="{url}">{inputs}'
            '<noscript><button type="submit">Continue to eSewa</button></noscript></form>'
            "<script>document.getElementById('esewa-form').submit();</script>"
        )

    # ------------------------------------------------------------------
    # verify — signature check + status confirmation
    # ------------------------------------------------------------------

    def verify(self, params: Dict[str, str]) -> TransactionResult:
        """Verify an eSewa success/failure redirect.

        1. Signature check on the returned signed fields (forgery guard).
        2. Server-to-server status check — only ``COMPLETE`` is a payment.
        """
        import requests  # optional dependency, imported lazily

        transaction_uuid = params.get("transaction_uuid", "")
        total_amount = params.get("total_amount", "")
        product_code = params.get("product_code", "")
        status = params.get("status", "")
        signature = params.get("signature", "")
        returned_field_names = params.get("signed_field_names", SIGNED_FIELD_NAMES)

        if not all([transaction_uuid, total_amount, product_code, signature]):
            logger.warning("eSewa verify missing params: %s", params.keys())
            return TransactionResult(ok=False, error="Missing callback params")

        if returned_field_names != SIGNED_FIELD_NAMES:
            return TransactionResult(ok=False, error="Unexpected signed_field_names")

        fields = {
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
        }
        if not self._check_signature(fields, signature, self.secret_key):
            logger.warning(
                "eSewa verify signature mismatch: uuid=%s got=%s",
                transaction_uuid, signature,
            )
            return TransactionResult(ok=False, error="Signature mismatch")

        # Server-to-server status confirmation (never trust the browser alone).
        try:
            resp = requests.get(
                _STATUS_ENDPOINTS.get(self.environment, _STATUS_ENDPOINTS["TEST"]),
                params={
                    "product_code": product_code,
                    "total_amount": total_amount,
                    "transaction_uuid": transaction_uuid,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.exception("eSewa status check failed: %s", exc)
            return TransactionResult(ok=False, error=f"Status check failed: {exc}")

        remote_status = str(data.get("status", "")).upper()
        ok = remote_status == "COMPLETE"
        logger.info(
            "eSewa verify: uuid=%s remote_status=%s response=%s",
            transaction_uuid, remote_status, data,
        )
        return TransactionResult(
            ok=ok,
            transaction_id=transaction_uuid,
            amount=int(round(float(total_amount or 0) * 100)),  # paisa
            status=remote_status or status,
            raw=data,
        )

    def webhook(self, body: Dict, signature: Optional[str] = None) -> TransactionResult:
        return self.verify(body)
