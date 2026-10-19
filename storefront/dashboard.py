"""Owner / admin dashboard: sales overview, filtering, order confirmation."""
import csv
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import SellerProfile, User
from catalog.models import Category, Product, ProductImage, ProductVariant
from catalog.validators import ProductImageValidator
from orders.models import Order, OrderItem

from .views import _nav


def _filtered_orders(request):
    """Orders filtered by the dashboard filter bar (status, payment, province, date, search)."""
    qs = Order.objects.select_related("customer").prefetch_related("items").order_by("-created_at")
    get = request.GET
    if get.get("status"):
        qs = qs.filter(status=get["status"])
    if get.get("payment_status"):
        qs = qs.filter(payment_status=get["payment_status"])
    if get.get("payment_method"):
        qs = qs.filter(payment_method=get["payment_method"])
    if get.get("province"):
        qs = qs.filter(province=get["province"])
    if get.get("q"):
        term = get["q"].strip()
        qs = qs.filter(
            Q(order_number__icontains=term) | Q(customer__username__icontains=term)
            | Q(full_name__icontains=term) | Q(phone__icontains=term)
        )
    if get.get("date_from"):
        qs = qs.filter(created_at__date__gte=get["date_from"])
    if get.get("date_to"):
        qs = qs.filter(created_at__date__lte=get["date_to"])
    return qs


def _page_links(page, edges: int = 1, around: int = 1):
    """Elided page numbers around the current page: 1 … 3 4 5 … 12."""
    n = page.paginator.num_pages
    cur = page.number
    wanted = set()
    wanted |= set(range(1, min(edges, n) + 1))
    wanted |= set(range(max(1, cur - around), min(n, cur + around) + 1))
    wanted |= set(range(max(1, n - edges + 1), n + 1))
    result, prev = [], 0
    for num in sorted(wanted):
        if num - prev > 1:
            result.append("…")
        result.append(num)
        prev = num
    return result


def _sales_stats(qs):
    revenue_qs = qs.exclude(status=Order.Status.CANCELLED)
    today = timezone.localdate()
    agg = revenue_qs.aggregate(
        revenue=Sum("total"), orders=Count("id"),
        pending_pay=Count("id", filter=Q(payment_status=Order.PaymentStatus.PENDING)),
        confirmed=Count("id", filter=Q(status=Order.Status.CONFIRMED)),
    )
    by_method = {
        r["payment_method"]: (r["m_count"], r["m_total"])
        for r in revenue_qs.values("payment_method").annotate(m_count=Count("id"), m_total=Sum("total"))
    }
    return {
        "revenue": agg["revenue"] or 0,
        "orders": agg["orders"],
        "pending_pay": agg["pending_pay"],
        "confirmed": agg["confirmed"],
        "today_revenue": revenue_qs.filter(created_at__date=today).aggregate(s=Sum("total"))["s"] or 0,
        "today_orders": revenue_qs.filter(created_at__date=today).count(),
        "by_method": by_method,
    }


def _week_chart():
    days, labels = [], []
    start = timezone.localdate() - timedelta(days=6)
    for i in range(7):
        d = start + timedelta(days=i)
        total = (
            Order.objects.exclude(status=Order.Status.CANCELLED)
            .filter(created_at__date=d).aggregate(s=Sum("total"))["s"] or 0
        )
        days.append(total)
        labels.append(d.strftime("%a"))
    peak = max([float(v) for v in days] + [1.0])
    return [
        {"label": label, "value": float(value), "pct": round(float(value) / peak * 100, 1)}
        for label, value in zip(labels, days, strict=True)
    ]


def _home_context(request):
    """Overview page only: numbers, alerts and a short recent-orders list.
    Everything else lives on its own page (orders / products / add / sales)."""
    qs = _filtered_orders(request)
    ctx = {
        "stats": _sales_stats(qs),
        "recent": qs[:5],
        "low_stock": Product.objects.filter(stock_quantity__lte=5).order_by("stock_quantity")[:8],
        # Single-seller store: the admin is the supplier, so staff never count
        # as customers here.
        "customers": User.objects.filter(role=User.Roles.CUSTOMER, is_staff=False).count(),
        "products": Product.objects.filter(is_active=True).count(),
    }
    ctx.update(_nav(request))
    return ctx


def _blank_variant_row():
    """One empty variant row, so the form always shows a place to type."""
    return {"id": "", "name": "", "price": "", "stock": ""}


def _parse_variant_rows(request):
    """Read the repeated variant rows (id / name / price / quantity) from POST.

    Returns ``(rows, errors, parsed)``: ``rows`` keeps the raw typed values so
    the form can be re-rendered after an error, ``errors`` holds one plain
    message per problem (numbered like the rows the seller sees) and ``parsed``
    holds the ready-to-save variants (``id`` of the stored row when the form
    posted one, ``Decimal`` price, ``int`` quantity).  Untouched rows are
    skipped, so the empty row the form always renders is harmless — the hidden
    id alone never keeps a row alive, so clearing a stored variant's fields
    removes it from the product.
    """
    names = request.POST.getlist("variant_name")
    prices = request.POST.getlist("variant_price")
    stocks = request.POST.getlist("variant_stock")
    ids = request.POST.getlist("variant_id")
    rows, errors, parsed, seen = [], [], [], set()

    for index in range(max(len(names), len(prices), len(stocks))):
        raw = {
            "id": (ids[index] if index < len(ids) else "").strip(),
            "name": (names[index] if index < len(names) else "").strip(),
            "price": (prices[index] if index < len(prices) else "").strip(),
            "stock": (stocks[index] if index < len(stocks) else "").strip(),
        }
        if not any(raw[field] for field in ("name", "price", "stock")):
            continue
        label = f"Variant {index + 1}"
        rows.append(dict(raw))

        variant_id = None
        if raw["id"]:
            try:
                variant_id = int(raw["id"])
            except ValueError:
                errors.append(f"{label}: this row is not valid — reload the page and try again.")

        name = raw["name"]
        if not name:
            errors.append(f"{label}: enter a variant name.")
        elif len(name) > 255:
            errors.append(f"{label}: name is too long (255 characters max).")
        elif name.lower() in seen:
            errors.append(f"{label}: “{name}” is already used — give every variant its own name.")
        else:
            seen.add(name.lower())

        price = None
        if not raw["price"]:
            errors.append(f"{label}: enter a price.")
        else:
            try:
                price = Decimal(raw["price"])
                if price < 0 or price.as_tuple().exponent < -2:
                    raise ValueError
            except Exception:
                errors.append(f"{label}: price must be a number like 999 or 999.50.")
                price = None
            else:
                # DecimalField(max_digits=10, decimal_places=2) can hold no more.
                if price >= Decimal("100000000"):
                    errors.append(f"{label}: price is too large.")
                    price = None

        stock = 0
        if raw["stock"]:
            try:
                stock = int(raw["stock"])
                if stock < 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{label}: quantity must be a whole number of units (0 or more).")
                stock = 0

        if name and price is not None:
            parsed.append({"id": variant_id, "name": name, "price": price, "stock": stock})

    return rows, errors, parsed


def _add_product_page(request, errors=None, values=None):
    """Render the standalone add-product page (keeps typed values on errors)."""
    ctx = {
        "categories": Category.objects.filter(is_active=True).order_by("name"),
        "form_errors": errors or [],
        "form_values": values or {},
        "variant_rows": (values or {}).get("variants") or [_blank_variant_row()],
    }
    ctx.update(_nav(request))
    return render(request, "storefront/dashboard_add_product.html", ctx)


def _store_profile(user):
    """The single supplier profile (single-seller store: admin = supplier)."""
    profile = SellerProfile.objects.filter(user=user).first() or SellerProfile.objects.first()
    if profile is None:
        profile = SellerProfile.objects.create(
            user=user,
            business_name="Nismita Craft Studio",
            business_phone="+977 970-8909514",
            address="Narephate - 32",
            city="Kathmandu",
            country="Nepal",
            is_verified=True,
        )
    return profile


def _product_form_values(request):
    """The plain product fields the dashboard's add and edit forms share."""
    return {
        key: request.POST.get(key, "").strip()
        for key in ("name", "category", "price", "stock", "description")
    }


def _validate_product_form(request, values, allow_category=None):
    """Validate the shared add / edit fields.

    Returns ``(errors, category, price, stock, valid_images, variants)`` and
    fills ``values["variants"]`` with the raw rows so the form re-renders
    exactly as typed.  ``allow_category`` is a primary key the caller accepts
    even if that category has since been deactivated — an edit must be able to
    keep the product's own category.
    """
    errors = []

    if not values["name"]:
        errors.append("Enter a product name.")

    category = None
    if not values["category"]:
        errors.append("Choose a category.")
    else:
        category = Category.objects.filter(pk=values["category"]).first()
        if category is None or (not category.is_active and category.pk != allow_category):
            errors.append("The chosen category does not exist.")
            category = None

    price = None
    if not values["price"]:
        errors.append("Enter a price.")
    else:
        try:
            price = Decimal(values["price"])
            if price < 0 or price.as_tuple().exponent < -2:
                raise ValueError
        except Exception:
            errors.append("Price must be a number like 999 or 999.50.")
            price = None
        # DecimalField(max_digits=10, decimal_places=2) can hold no more.
        if price is not None and price >= Decimal("100000000"):
            errors.append("Price is too large.")
            price = None

    stock = 0
    if values["stock"]:
        try:
            stock = int(values["stock"])
            if stock < 0:
                raise ValueError
        except ValueError:
            errors.append("Stock must be a whole number of units (0 or more).")
            stock = 0

    images = request.FILES.getlist("images")
    # Keep the old single-file field compatible with existing clients/bookmarks.
    if not images and request.FILES.get("image"):
        images = [request.FILES["image"]]
    if len(images) > 8:
        errors.append("Upload no more than 8 product photos.")
        images = images[:8]

    image_validator = ProductImageValidator()
    valid_images = []
    for image in images:
        try:
            image_validator(image)
        except Exception as exc:
            errors.append(getattr(exc, "messages", [str(exc)])[0])
            continue
        valid_images.append(image)

    variant_rows, variant_errors, variants = _parse_variant_rows(request)
    values["variants"] = variant_rows
    errors.extend(variant_errors)

    return errors, category, price, stock, valid_images, variants


def _add_product(request):
    """Add a product straight from the dashboard: few fields, plain errors."""
    values = _product_form_values(request)
    errors, category, price, stock, valid_images, variants = _validate_product_form(request, values)

    if errors:
        return _add_product_page(request, errors, values)

    name = values["name"]

    with transaction.atomic():
        base_slug = slugify(name) or "product"
        slug, n = base_slug, 2
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{n}"
            n += 1
        sku = f"NC-{uuid.uuid4().hex[:8].upper()}"
        while Product.objects.filter(sku=sku).exists():
            sku = f"NC-{uuid.uuid4().hex[:8].upper()}"

        product = Product.objects.create(
            seller=_store_profile(request.user),
            category=category,
            name=name,
            slug=slug,
            sku=sku,
            short_description=values["description"][:500],
            description=values["description"],
            price=price,
            stock_quantity=stock,
            is_active=True,
            is_available=True,
        )
        for order, image in enumerate(valid_images):
            ProductImage.objects.create(
                product=product,
                image=image,
                alt_text=name,
                is_primary=order == 0,
                display_order=order,
            )
        for index, variant in enumerate(variants, start=1):
            ProductVariant.objects.create(
                product=product,
                name=variant["name"],
                sku=f"{sku}-V{index:02d}",
                price=variant["price"],
                stock_quantity=variant["stock"],
                is_active=True,
            )

    if variants:
        messages.success(
            request,
            f"“{name}” was added to your shop with {len(variants)} variant"
            f"{'s' if len(variants) > 1 else ''}."
        )
    else:
        messages.success(request, f"“{name}” was added to your shop.")
    return redirect("storefront:dashboard-products")


def _edit_product_values(product):
    """Current stored values as the strings the edit form posts back."""
    return {
        "name": product.name,
        "category": str(product.category_id),
        "price": str(product.price),
        "stock": str(product.stock_quantity),
        "description": product.description,
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "variants": [
            {"id": str(v.pk), "name": v.name, "price": str(v.price), "stock": str(v.stock_quantity)}
            for v in product.variants.all()
        ] or [_blank_variant_row()],
    }


def _edit_image_rows(product, removed_ids=()):
    """The product's photos for the edit form, with the ticked-to-delete state."""
    removed = {str(pk) for pk in removed_ids}
    return [
        {"id": image.pk, "url": image.image.url, "primary": image.is_primary, "removed": str(image.pk) in removed}
        for image in product.images.all()
    ]


def _edit_product_page(request, product, errors=None, values=None):
    """Render the edit page; ``values`` keeps what was typed after an error."""
    values = values if values is not None else _edit_product_values(product)
    ctx = {
        "product": product,
        # The product's own category stays selectable even if it was deactivated.
        "categories": Category.objects.filter(Q(is_active=True) | Q(pk=product.category_id)).order_by("name"),
        "form_errors": errors or [],
        "form_values": values,
        "variant_rows": values.get("variants") or [_blank_variant_row()],
        "image_rows": _edit_image_rows(product, values.get("removed_images", ())),
    }
    ctx.update(_nav(request))
    return render(request, "storefront/dashboard_edit_product.html", ctx)


def _edit_product(request, product):
    """Apply the edit form: same validation as add, then sync variants/photos."""
    values = _product_form_values(request)
    errors, category, price, stock, valid_images, variants = _validate_product_form(
        request, values, allow_category=product.category_id
    )
    values["is_active"] = request.POST.get("is_active") == "1"
    values["is_featured"] = request.POST.get("is_featured") == "1"

    remove_ids = []
    for pk in request.POST.getlist("remove_image"):
        try:
            remove_ids.append(int(pk))
        except (TypeError, ValueError):
            continue
    values["removed_images"] = [str(pk) for pk in remove_ids]

    # The form posts a marker with the variant section, so a submission without
    # it (a partial or hand-built POST) can never wipe the stored variants.
    sync_variants = request.POST.get("variant_sync") == "1"
    kept_variant_ids = set()
    if sync_variants and not errors:
        own_variant_ids = set(product.variants.values_list("pk", flat=True))
        for row in variants:
            variant_id = row.get("id")
            if variant_id is None:
                continue
            if variant_id not in own_variant_ids:
                errors.append(
                    "A variant row points at a variant that is not part of this product — "
                    "reload the page and try again."
                )
                break
            kept_variant_ids.add(variant_id)

    if sync_variants and not errors:
        # Order lines keep their variant forever (PROTECT), so one that was
        # ever bought must stay — explain instead of crashing on delete.
        ordered_names = (
            OrderItem.objects.filter(variant__product=product)
            .exclude(variant_id__in=kept_variant_ids)
            .values_list("variant__name", flat=True)
            .distinct()
        )
        if ordered_names:
            listed = ", ".join(f"“{name}”" for name in ordered_names)
            errors.append(
                f"{listed} already appear in past orders, so those variants can't be removed — "
                "keep their rows instead."
            )

    if product.images.exclude(pk__in=remove_ids).count() + len(valid_images) > 8:
        errors.append("A product can have at most 8 photos — untick more before saving.")

    if errors:
        if not sync_variants and "variant_name" not in request.POST:
            # Nothing about the variants was posted: show the stored rows again.
            values["variants"] = _edit_product_values(product)["variants"]
        return _edit_product_page(request, product, errors, values)

    with transaction.atomic():
        product.category = category
        product.name = values["name"]
        product.short_description = values["description"][:500]
        product.description = values["description"]
        product.price = price
        product.stock_quantity = stock
        product.is_active = values["is_active"]
        product.is_featured = values["is_featured"]
        product.save()

        if sync_variants:
            existing = {v.pk: v for v in product.variants.all()}
            used_skus = {v.sku for v in existing.values()}
            sequence = 1
            for row in variants:
                stored = existing.get(row.get("id"))
                if stored is not None:
                    stored.name = row["name"]
                    stored.price = row["price"]
                    stored.stock_quantity = row["stock"]
                    stored.save()
                    continue
                sku = f"{product.sku}-V{sequence:02d}"
                while sku in used_skus:
                    sequence += 1
                    sku = f"{product.sku}-V{sequence:02d}"
                used_skus.add(sku)
                sequence += 1
                ProductVariant.objects.create(
                    product=product,
                    name=row["name"],
                    sku=sku,
                    price=row["price"],
                    stock_quantity=row["stock"],
                    is_active=True,
                )
            doomed_ids = set(existing) - kept_variant_ids
            if doomed_ids:
                product.variants.filter(pk__in=doomed_ids).delete()

        if remove_ids:
            for image in product.images.filter(pk__in=remove_ids):
                image.image.delete(save=False)
                image.delete()
        next_order = product.images.count()
        for offset, image in enumerate(valid_images):
            ProductImage.objects.create(
                product=product,
                image=image,
                alt_text=product.name,
                is_primary=False,
                display_order=next_order + offset,
            )
        # Exactly one cover photo: promote the first one left if the old cover
        # was ticked for deletion.
        remaining = list(product.images.order_by("display_order", "pk"))
        if remaining and not any(image.is_primary for image in remaining):
            remaining[0].is_primary = True
            remaining[0].save(update_fields=["is_primary"])

    messages.success(request, f"“{product.name}” was updated.")
    return redirect("storefront:dashboard-products")


@staff_member_required
def dashboard_payment_screenshot(request, pk):
    """Serve payment screenshots to staff without exposing the media directory."""
    order = get_object_or_404(Order, pk=pk)
    if not order.payment_screenshot:
        return HttpResponseNotFound("Payment screenshot not found.")
    return FileResponse(order.payment_screenshot.open("rb"), content_type="image/*")


@staff_member_required
def dashboard_home(request):
    return render(request, "storefront/dashboard.html", _home_context(request))


@staff_member_required
def dashboard_add_product(request):
    """Standalone page for adding a product (admin = supplier)."""
    if request.method == "POST":
        return _add_product(request)
    return _add_product_page(request)


@staff_member_required
def dashboard_edit_product(request, pk):
    """Edit an existing product from the dashboard (same form as add)."""
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        return _edit_product(request, product)
    return _edit_product_page(request, product)


@staff_member_required
def dashboard_products(request):
    """All products with stock — lowest stock listed first."""
    ctx = {
        "all_products": (
            Product.objects.select_related("category")
            .prefetch_related("variants")
            .order_by("stock_quantity", "name")
        ),
        "low_stock": Product.objects.filter(stock_quantity__lte=5).order_by("stock_quantity"),
        "product_count": Product.objects.filter(is_active=True).count(),
    }
    ctx.update(_nav(request))
    return render(request, "storefront/dashboard_products.html", ctx)


def _iso_date(value):
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


@staff_member_required
def dashboard_report(request):
    """Sales report: filterable totals, daily breakdown and best sellers."""
    get = request.GET
    qs = Order.objects.exclude(status=Order.Status.CANCELLED)

    date_from, date_to = _iso_date(get.get("date_from")), _iso_date(get.get("date_to"))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    # Quick presets only apply when no custom dates are given.
    preset = get.get("range")
    today = timezone.localdate()
    if not date_from and not date_to:
        if preset == "today":
            qs = qs.filter(created_at__date=today)
        elif preset == "7d":
            qs = qs.filter(created_at__date__gte=today - timedelta(days=6))
        elif preset == "30d":
            qs = qs.filter(created_at__date__gte=today - timedelta(days=29))

    method = get.get("payment_method")
    if method in Order.PaymentMethod.values:
        qs = qs.filter(payment_method=method)

    totals = qs.aggregate(revenue=Sum("total"), orders=Count("id"))
    revenue, order_count = totals["revenue"] or Decimal("0"), totals["orders"] or 0
    units = OrderItem.objects.filter(order__in=qs).aggregate(u=Sum("quantity"))["u"] or 0

    daily = (
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("-day")[:31]
    )
    top_products = (
        OrderItem.objects.filter(order__in=qs)
        .values("product_id", "product_name", "sku")
        .annotate(qty=Sum("quantity"), revenue=Sum("total_price"), orders=Count("order", distinct=True))
        .order_by("-qty")[:10]
    )
    by_method = qs.values("payment_method").annotate(n=Count("id"), s=Sum("total")).order_by("-s")

    ctx = {
        "revenue": revenue,
        "order_count": order_count,
        "units": units,
        "aov": (revenue / order_count) if order_count else Decimal("0"),
        "daily": daily,
        "top_products": top_products,
        "by_method": by_method,
        "payment_methods": Order.PaymentMethod.choices,
        "f_date_from": get.get("date_from", ""),
        "f_date_to": get.get("date_to", ""),
        "f_method": method or "",
        "f_range": preset or "",
        "filters_active": bool(get),
    }
    ctx.update(_nav(request))
    return render(request, "storefront/dashboard_report.html", ctx)


def _csv_cell(value):
    """Return ``value`` as a spreadsheet-safe cell.

    Excel/Sheets execute a cell that starts with ``=``, ``+``, ``-``, ``@``, TAB
    or CR, so a customer named ``=cmd|'/c calc'!A1`` (or a crafted province)
    became a formula the moment staff opened the export.  Neutralise those by
    prefixing an apostrophe — except for plain numbers, which must stay numeric.
    """
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        try:
            float(text)
        except ValueError:
            return "'" + text
    return text


@staff_member_required
def dashboard_orders(request):
    qs = _filtered_orders(request)
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales.csv"'
        w = csv.writer(response)
        w.writerow(["Order", "Date", "Customer", "Phone", "Province", "District", "City",
                    "Payment", "PayStatus", "Status", "Subtotal", "Shipping", "Total"])
        for o in qs:
            w.writerow([_csv_cell(o.order_number), _csv_cell(o.created_at), _csv_cell(o.customer.username),
                        _csv_cell(o.phone), _csv_cell(o.province), _csv_cell(o.district), _csv_cell(o.city),
                        _csv_cell(o.payment_method), _csv_cell(o.payment_status), _csv_cell(o.status),
                        o.subtotal, o.shipping_cost, o.total])
        return response
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    ctx = {
        "orders": page.object_list, "page_obj": page, "count": qs.count(),
        "page_links": _page_links(page),
        "stats": _sales_stats(qs),
        "chart": _week_chart(),
        "statuses": Order.Status.choices,
        "payment_methods": Order.PaymentMethod.choices,
        "payment_statuses": Order.PaymentStatus.choices,
        "provinces": sorted({o["province"] for o in Order.objects.values("province") if o["province"]}),
    }
    ctx.update(_nav(request))
    return render(request, "storefront/dashboard_orders.html", ctx)


@staff_member_required
def dashboard_order(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer", "confirmed_by"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        previous_status = order.status
        
        if action == "confirm":
            order.payment_status = Order.PaymentStatus.VERIFIED
            order.status = Order.Status.CONFIRMED
            order.confirmed_at, order.confirmed_by = timezone.now(), request.user
            messages.success(request, f"{order.order_number} payment verified & order confirmed.")
        elif action == "verify_payment":
            order.payment_status = Order.PaymentStatus.VERIFIED
            messages.success(request, f"Payment verified for {order.order_number}.")
        elif action == "reject_payment":
            order.payment_status = Order.PaymentStatus.REJECTED
            order.status = Order.Status.CANCELLED
            messages.warning(request, f"Payment rejected — {order.order_number} cancelled.")
        elif action in ("process", "ship", "deliver"):
            order.status = {"process": "PROCESSING", "ship": "SHIPPED", "deliver": "DELIVERED"}[action]
            messages.success(request, f"{order.order_number} → {order.status}.")
        elif action == "cancel":
            order.status = Order.Status.CANCELLED
            messages.warning(request, f"{order.order_number} cancelled.")
        
        with transaction.atomic():
            order.save(update_fields=["status", "payment_status", "confirmed_at", "confirmed_by", "updated_at"])
            
            # Restock when order is cancelled (only if it wasn't already cancelled)
            if order.status == Order.Status.CANCELLED and previous_status != Order.Status.CANCELLED:
                order_items = OrderItem.objects.filter(order=order)
                for item in order_items:
                    if item.variant:
                        ProductVariant.objects.filter(pk=item.variant.pk).update(
                            stock_quantity=models.F('stock_quantity') + item.quantity
                        )
                    else:
                        Product.objects.filter(pk=item.product.pk).update(
                            stock_quantity=models.F('stock_quantity') + item.quantity
                        )
        
        return redirect("storefront:dashboard-order", pk=order.pk)
    flow = ["PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"]
    if order.status == "CANCELLED":
        timeline = [(s, False) for s in flow]
    else:
        idx = flow.index(order.status)
        timeline = [(s, i <= idx) for i, s in enumerate(flow)]
    ctx = {"order": order, "timeline": timeline}
    ctx.update(_nav(request))
    return render(request, "storefront/dashboard_order.html", ctx)
