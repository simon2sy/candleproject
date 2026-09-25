from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class HealthEndpointTests(TestCase):
    def test_liveness_endpoint_is_public(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_endpoint_checks_database(self):
        response = self.client.get(reverse("readyz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})


class CustomerPreviewAccessTests(TestCase):
    """Only signed-in staff may temporarily inspect the customer storefront."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="preview_admin",
            email="preview_admin@example.com",
            password="PreviewAdmin@2026",
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="preview_customer",
            email="preview_customer@example.com",
            password="PreviewCustomer@2026",
        )
        self.start_url = reverse("storefront:customer-preview-start")
        self.return_url = reverse("storefront:customer-preview-return")

    def test_customer_cannot_start_or_return_customer_preview(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(self.start_url).status_code, 302)
        self.assertNotIn("customer_preview", self.client.session)
        self.assertEqual(self.client.post(self.return_url).status_code, 302)
        self.assertNotIn("customer_preview", self.client.session)

    def test_anonymous_user_cannot_start_customer_preview(self):
        response = self.client.post(self.start_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.assertNotIn("customer_preview", self.client.session)

    def test_staff_preview_is_temporary_and_staff_only_actions_work(self):
        self.client.force_login(self.staff)
        # GET cannot change privileged state.
        self.assertEqual(self.client.get(self.start_url).status_code, 405)
        # Ordinary storefront browsing remains blocked until preview is explicitly started.
        home = reverse("storefront:home")
        self.assertEqual(self.client.get(home).status_code, 302)
        self.assertEqual(self.client.post(self.start_url).status_code, 302)
        response = self.client.get(home)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "viewing the website from the customer side")
        self.assertContains(response, self.return_url)
        self.assertContains(response, 'class="menu"')
        self.assertContains(response, 'class="mobilebar"')

        returned = self.client.post(self.return_url)
        self.assertRedirects(returned, reverse("storefront:dashboard"))
        self.assertNotIn("customer_preview", self.client.session)
        self.assertEqual(self.client.get(home).status_code, 302)
