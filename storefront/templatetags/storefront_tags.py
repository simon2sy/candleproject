"""Storefront template tags."""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def esewa_form(context, order):
    """Render the auto-submitting eSewa form HTML for ``order``."""
    from orders.gateways import get_gateway, gateway_ready

    request = context["request"]
    gateway = get_gateway("ESEWA")
    if gateway is None or not gateway_ready(gateway):
        return ""
    from django.urls import reverse

    callback = request.build_absolute_uri(reverse("storefront:esewa-callback"))
    return gateway.get_initiate_form(order, callback)
