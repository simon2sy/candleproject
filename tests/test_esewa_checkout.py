"""eSewa checkout integration: gateway-on renders the auto-submitting form,
gateway-off falls back to the manual WhatsApp flow, and the callback view
verifies + confirms the order (idempotently) while rejecting forgeries."""
import base64
import hashlib
import hmac
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from catalog.models import Category, Product
from orders.gateways.esewa import SIGNED_FIELD_NAMES
from orders.models import Order
from tests.checkout import add_to_cart, checkout_payload
from tests.helpers import make_seller, make_user

SECRET = "test-secret-key"


def _sign(fields: dict, secret: str = SECRET) -> str:
    message = ",".join(f"{n}={fields[n]}" for n in SIGNED_FIELD_NAMES.split(","))
    return base64.b64encode(
        hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()


def _esewa_env():
    return {
        "ESEWA_MERCHANT_ID": "EPAYTEST",
        "ESEWA_SECRET_KEY": SECRET,
        "ESEWA_ENVIRONMENT": "TEST",
    }


class GatewayOnCheckoutTest(TestCase):
    """With credentials set, choosing eSewa at checkout renders the form POST."""

    def setUp(self):
        patcher = mock.patch.dict("os.environ", _esewa_env())
        patcher.start()
        self.addCleanup(patcher.stop)

        self.seller_user, self.seller_profile = make_seller("seller_eso")
        self.customer = make_user("buyer_eso")
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=Category.objects.create(name="Eso Cat", slug="eso-cat"),
            name="Gateway Candle",
            slug="gateway-candle",
            sku="GW-001",
            price=Decimal("1200.00"),
            stock_quantity=5,
        )
        self.client.force_login(self.customer)
        add_to_cart(self.client, self.product, quantity=1)

    def test_checkout_renders_auto_submitting_form(self):
        resp = self.client.post("/checkout/", checkout_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "storefront/esewa_redirect.html")
        self.assertContains(resp, "rc-epay.esewa.com.np/api/epay/main/v2/form")
        self.assertContains(resp, 'value="%s"' % resp.context["order_number"])
        # stock already reserved even though the customer is on eSewa's page
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)
        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_gateway_off_falls_back_to_manual(self):
        # simulate missing credentials
        with mock.patch.dict("os.environ", {"ESEWA_MERCHANT_ID": "", "ESEWA_SECRET_KEY": ""}):
            resp = self.client.post("/checkout/", checkout_payload(), follow=True)
        self.assertEqual(resp.status_code, 200)
        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        messages = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("WhatsApp" in str(m) for m in messages))


class CallbackVerifyTest(TestCase):
    """POST /payment/esewa/callback/ — the URL eSewa's success_url points to."""

    def setUp(self):
        patcher = mock.patch.dict("os.environ", _esewa_env())
        patcher.start()
        self.addCleanup(patcher.stop)

        self.seller_user, self.seller_profile = make_seller("seller_escb")
        self.customer = make_user("buyer_escb")
        self.order = Order.objects.create(
            customer=self.customer,
            order_number="ORD-CB001",
            status=Order.Status.PENDING,
            payment_method=Order.PaymentMethod.ESEWA,
            total=Decimal("1500.50"),
            shipping_cost=Decimal("0.00"),
            full_name="Ram Shrestha",
            phone="9800000000",
            province="Bagmati",
            district="Kathmandu",
            city="Kathmandu",
            address_line="Mg Road",
        )

    def _callback_data(self, amount="1500.50", uuid="ORD-CB001", secret=SECRET):
        fields = {
            "total_amount": amount,
            "transaction_uuid": uuid,
            "product_code": "EPAYTEST",
        }
        return {
            **fields,
            "status": "COMPLETE",
            "signed_field_names": SIGNED_FIELD_NAMES,
            "signature": _sign(fields, secret),
        }

    def _verify_remote(self, status="COMPLETE"):
        resp = mock.Mock()
        resp.raise_for_status = mock.Mock()
        resp.json.return_value = {"status": status}
        return mock.patch("requests.get", return_value=resp)

    def test_valid_callback_verifies_and_confirms(self):
        with self._verify_remote("COMPLETE"):
            resp = self.client.post("/payment/esewa/callback/", self._callback_data())
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.VERIFIED)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertIsNotNone(self.order.confirmed_at)

    def test_forged_signature_leaves_order_pending(self):
        with self._verify_remote("COMPLETE"):
            self.client.post("/payment/esewa/callback/", self._callback_data(secret="attacker"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_underpayment_rejected(self):
        # attacker pays Rs 10 but signs it correctly — remote status check is
        # also COMPLETE, so the amount comparison in the view must catch it
        with self._verify_remote("COMPLETE"):
            self.client.post("/payment/esewa/callback/", self._callback_data(amount="10.00"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    def test_callback_is_idempotent(self):
        with self._verify_remote("COMPLETE"):
            self.client.post("/payment/esewa/callback/", self._callback_data())
        with self._verify_remote("COMPLETE"):
            resp = self.client.post("/payment/esewa/callback/", self._callback_data())
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.VERIFIED)
        self.assertEqual(Order.objects.filter(order_number="ORD-CB001").count(), 1)

    def test_unknown_order_redirects_home(self):
        with self._verify_remote("COMPLETE"):
            resp = self.client.post("/payment/esewa/callback/", self._callback_data(uuid="ORD-NOPE"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/")


class UnderpaymentGuardTest(TestCase):
    """The amount check in the view: signed paisa amount must cover the total."""

    def test_view_rejects_partial_amount(self):
        patcher = mock.patch.dict("os.environ", _esewa_env())
        patcher.start()
        self.addCleanup(patcher.stop)

        seller_user, profile = make_seller("seller_upg")
        customer = make_user("buyer_upg")
        order = Order.objects.create(
            customer=customer,
            order_number="ORD-UPG1",
            status=Order.Status.PENDING,
            total=Decimal("999.00"),
            shipping_cost=Decimal("0.00"),
            full_name="R", phone="98", province="Bagmati",
            district="Kathmandu", city="KTM", address_line="X",
        )
        fields = {
            "total_amount": "500.00",
            "transaction_uuid": "ORD-UPG1",
            "product_code": "EPAYTEST",
        }
        data = {
            **fields,
            "status": "COMPLETE",
            "signed_field_names": SIGNED_FIELD_NAMES,
            "signature": _sign(fields),
        }
        resp_mock = mock.Mock()
        resp_mock.raise_for_status = mock.Mock()
        resp_mock.json.return_value = {"status": "COMPLETE"}
        with mock.patch("requests.get", return_value=resp_mock):
            self.client.post("/payment/esewa/callback/", data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
