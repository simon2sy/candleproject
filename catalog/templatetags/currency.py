from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _format_money(value):
    """Format a number as Nepalese Rupees with 2 decimal places."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "Rs {:,.2f}".format(v)


@register.filter(name="money")
def money_filter(value):
    return _format_money(value)


@register.simple_tag
def money_tag(value):
    return _format_money(value)
