"""SEO template tags: absolute/canonical URLs + safe JSON-LD output."""
from __future__ import annotations

import json

from django import template
from django.utils.safestring import mark_safe

from storefront.seo import absolute_url, canonical_url

register = template.Library()


@register.simple_tag(takes_context=True)
def canonical(context) -> str:
    request = context.get("request")
    return canonical_url(request, request.path if request else "/")


@register.simple_tag(takes_context=True)
def absolute(context, path: str) -> str:
    return absolute_url(context.get("request"), path or "/")


@register.filter(name="json_ld")
def json_ld(value) -> str:
    """Serialize Python data as safe inline JSON-LD (no HTML escaping)."""
    return mark_safe(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
