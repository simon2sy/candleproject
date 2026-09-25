"""Tests for the eSewa ePay v2 gateway.

Covers:
- signature generation matches eSewa's documented HMAC-SHA256/base64 scheme
- initiate() builds a signed form payload
- verify() accepts a genuine signed + COMPLETE callback
- verify() rejects forged signatures, tampered amounts, and non-COMPLETE status
"""
import base64
import hashlib
import hmac
from unittest import mock

from django.test import TestCase

from orders.gateways.esewa import SIGNED_FIELD_NAMES, EsewaGateway


def _sign(fields: dict, secret: str) -> str:
    message = ",".join(f"{n}={fields[n]}" for n in SIGNED_FIELD_NAMES.split(","))
    return base64.b64encode(
        hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()


class SignatureTests(TestCase):
    def setUp(self):
        self.gw = EsewaGateway()
        self.gw.merchant_id = "EPAYTEST"
        self.gw.secret_key = "8gBm/:;EnhH.1/q"

    def test_signature_matches_documented_scheme(self):
        # The example from eSewa's docs: total_amount=100, uuid=abc, code=EPAYTEST
        fields = {"total_amount": "100", "transaction_uuid": "abc", "product_code": "EPAYTEST"}
        sig = self.gw._make_signature(fields)
        self.assertEqual(sig, _sign(fields, "8gBm/:;EnhH.1/q"))
        self.assertTrue(self.gw._check_signature(fields, sig, "8gBm/:;EnhH.1/q"))

    def test_check_signature_rejects_forged(self):
        fields = {"total_amount": "100", "transaction_uuid": "abc", "product_code": "EPAYTEST"}
        self.assertFalse(self.gw._check_signature(fields, "bogus==", "8gBm/:;EnhH.1/q"))

    def test_check_signature_rejects_wrong_secret(self):
        fields = {"total_amount": "100", "transaction_uuid": "abc", "product_code": "EPAYTEST"}
        sig = _sign(fields, "other-secret")
        self.assertFalse(self.gw._check_signature(fields, sig, "8gBm/:;EnhH.1/q"))


class InitiateTests(TestCase):
    def setUp(self):
        self.gw = EsewaGateway()
        self.gw.merchant_id = "EPAYTEST"
        self.gw.secret_key = "8gBm/:;EnhH.1/q"
        self.gw.callback_url = "https://shop.example.com/payment/esewa/callback/"

    def _order(self):
        from decimal import Decimal

        class O:  # minimal duck-typed order
            order_number = "ORD-TEST123"
            total = Decimal("1500.00")

        return O()

    def test_initiate_requires_credentials(self):
        self.gw.merchant_id = ""
        with self.assertRaises(RuntimeError):
            self.gw.initiate(self._order(), "https://shop.example.com/x/")

    def test_form_contains_signed_payload(self):
        html = self.gw.get_initiate_form(self._order(), "https://shop.example.com/x/")
        self.assertIn('name="transaction_uuid" value="ORD-TEST123"', html)
        self.assertIn('name="total_amount" value="1500.00"', html)
        self.assertIn('name="product_code" value="EPAYTEST"', html)
        self.assertIn('name="signed_field_names"', html)
        self.assertIn("action=\"https://rc-epay.esewa.com.np/api/epay/main/v2/form\"", html)
        self.assertIn("submit()", html)  # auto-submits

    def test_success_and_failure_urls(self):
        html = self.gw.get_initiate_form(self._order(), "")
        self.assertIn("action=success", html)
        self.assertIn("action=failure", html)


class VerifyTests(TestCase):
    def setUp(self):
        self.gw = EsewaGateway()
        self.gw.merchant_id = "EPAYTEST"
        self.gw.secret_key = "8gBm/:;EnhH.1/q"

    def _callback(self, amount="1500.50", status="COMPLETE", secret="8gBm/:;EnhH.1/q"):
        fields = {
            "total_amount": amount,
            "transaction_uuid": "ORD-TEST123",
            "product_code": "EPAYTEST",
        }
        return {
            **fields,
            "status": status,
            "signed_field_names": SIGNED_FIELD_NAMES,
            "signature": _sign(fields, secret),
        }

    def _verify_with_status(self, params, remote_status="COMPLETE"):
        resp = mock.Mock()
        resp.raise_for_status = mock.Mock()
        resp.json.return_value = {"status": remote_status}
        with mock.patch("requests.get", return_value=resp) as mget:
            result = self.gw.verify(params)
        return result, mget

    def test_valid_callback_is_complete(self):
        result, mget = self._verify_with_status(self._callback(), "COMPLETE")
        self.assertTrue(result.ok)
        self.assertEqual(result.transaction_id, "ORD-TEST123")
        self.assertEqual(result.amount, 150050)  # paisa
        # status check was actually called server-to-server
        self.assertIn("transaction_uuid", mget.call_args.kwargs["params"])

    def test_forged_signature_rejected(self):
        result, _ = self._verify_with_status(self._callback(secret="attacker-key"))
        self.assertFalse(result.ok)
        self.assertIn("Signature", result.error)

    def test_tampered_amount_rejected(self):
        params = self._callback(amount="1.00")
        # re-sign the tampered amount so the signature check passes but the
        # remote status check is what must fail (payment never existed)
        result, _ = self._verify_with_status(params, remote_status="NOT_FOUND")
        self.assertFalse(result.ok)

    def test_non_complete_status_rejected(self):
        result, _ = self._verify_with_status(self._callback(status="PENDING"), "PENDING")
        self.assertFalse(result.ok)

    def test_missing_params_rejected(self):
        result, _ = self._verify_with_status({"signature": "x"})
        self.assertFalse(result.ok)

    def test_unexpected_signed_fields_rejected(self):
        params = self._callback()
        params["signed_field_names"] = "total_amount,transaction_uuid"
        result, _ = self._verify_with_status(params)
        self.assertFalse(result.ok)
        self.assertIn("signed_field_names", result.error)
