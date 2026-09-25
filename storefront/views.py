"""Public storefront (Django templates) — Ukiyo-style layout, Nismita purple theme."""
import json
import logging
import uuid
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Address, User
from catalog.models import Category, Product, ProductVariant
from orders.gateways import TransactionResult, gateway_ready, get_gateway
from orders.models import Cart, CartItem, Order, OrderItem, Wishlist, WishlistItem
from orders.services import InsufficientStock, _display_price, place_order_from_cart
from orders.validators import validate_payment_screenshot

from .nepal import PROVINCES, PROVINCE_CHOICES

logger = logging.getLogger(__name__)


def _nav(request):
    ctx = {"nav_categories": Category.objects.filter(is_active=True, parent__isnull=True)[:6]}
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        ctx["cart_count"] = cart.count
    else:
        ctx["cart_count"] = sum(i.get("quantity", 0) for i in request.session.get("cart", []))
    return ctx


def _get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    return None


def _session_cart(request):
    return request.session.get("cart", [])


def _save_session_cart(request, items):
    request.session["cart"] = items
    request.session.modified = True


def _merge_session_cart(request):
    """On login: merge anonymous session cart into the user cart."""
    items = _session_cart(request)
    if not items or not request.user.is_authenticated:
        return
    cart, _ = Cart.objects.get_or_create(user=request.user)
    for entry in items:
        try:
            product = Product.objects.get(pk=entry["product"], is_active=True)
        except Product.DoesNotExist:
            continue
        variant = None
        if entry.get("variant"):
            variant = ProductVariant.objects.filter(pk=entry["variant"], product=product, is_active=True).first()
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, variant=variant, defaults={"quantity": entry.get("quantity", 1)}
        )
        if not created:
            item.quantity += entry.get("quantity", 1)
            item.save(update_fields=["quantity", "updated_at"])
    _save_session_cart(request, [])


@staff_member_required
@require_POST
def start_customer_preview(request):
    """Let a signed-in staff member temporarily browse the storefront as a shopper."""
    request.session["customer_preview"] = True
    return redirect("storefront:home")


@staff_member_required
@require_POST
def return_from_customer_preview(request):
    request.session.pop("customer_preview", None)
    return redirect("storefront:dashboard")


def _staff_guard(request):
    """Keep the owner out of buyer pages unless customer preview is explicitly active."""
    if request.user.is_staff and not request.session.get("customer_preview", False):
        return redirect("storefront:dashboard")
    return None


def home(request):
    g = _staff_guard(request)
    if g:
        return g
    base = Product.objects.filter(is_active=True).select_related("seller", "category").prefetch_related("tags", "images")
    ctx = {
        "featured": base.filter(is_featured=True)[:8],
        "latest": base.order_by("-created_at")[:8],
        "stats": {"products": Product.objects.filter(is_active=True).count(), "categories": Category.objects.filter(is_active=True).count()},
    }
    ctx.update(_nav(request))
    return render(request, "storefront/home.html", ctx)


def _filtered_products(params, category=None):
    qs = Product.objects.filter(is_active=True).select_related("seller", "category").prefetch_related("tags", "images")
    if category:
        ids = [category.id] + list(category.children.values_list("id", flat=True))
        qs = qs.filter(category_id__in=ids)
    s = params.get("search", "").strip()
    if s:
        qs = qs.filter(Q(name__icontains=s) | Q(description__icontains=s) | Q(sku__icontains=s))
    try:
        if params.get("min_price"):
            qs = qs.filter(price__gte=float(params["min_price"]))
        if params.get("max_price"):
            qs = qs.filter(price__lte=float(params["max_price"]))
    except ValueError:
        pass
    o = params.get("ordering")
    if o in ("price", "-price", "name", "-name"):
        qs = qs.order_by(o)
    else:
        qs = qs.order_by("-created_at")
    return qs


def shop(request, slug=None):
    g = _staff_guard(request)
    if g:
        return g
    category = get_object_or_404(Category, slug=slug, is_active=True) if slug else None
    page = Paginator(_filtered_products(request.GET, category), 12).get_page(request.GET.get("page"))
    ctx = {
        "products": page,
        "category": category,
        "categories": Category.objects.filter(is_active=True, parent__isnull=True).annotate(Count("products")),
        "search": request.GET.get("search", "").strip(),
        "min_price": request.GET.get("min_price", "").strip(),
        "max_price": request.GET.get("max_price", "").strip(),
        "ordering": request.GET.get("ordering", ""),
    }
    ctx.update(_nav(request))
    return render(request, "storefront/shop.html", ctx)


def detail(request, slug):
    g = _staff_guard(request)
    if g:
        return g
    product = get_object_or_404(
        Product.objects.select_related("seller", "category").prefetch_related("images", "variants", "attributes", "tags"),
        slug=slug, is_active=True,
    )
    related = (
        Product.objects.filter(is_active=True, category=product.category)
        .exclude(pk=product.pk)
        .select_related("category")
        .prefetch_related("images", "tags")[:4]
    )
    image_url = ""
    seo_image = product.primary_image
    if seo_image and seo_image.image:
        image_url = request.build_absolute_uri(seo_image.image.url)
    description = product.short_description or " ".join(product.description.split()) or f"Buy {product.name} for candle making or cold process soap making in Nepal."
    product_seo_schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": description[:5000],
        "sku": product.sku,
        "category": product.category.name,
        "brand": {"@type": "Brand", "name": "Nismita Craft Studio"},
        "url": request.build_absolute_uri(),
        "image": [image_url] if image_url else [],
        "offers": {
            "@type": "Offer",
            "url": request.build_absolute_uri(),
            "priceCurrency": "NPR",
            "price": str(product.price),
            "availability": "https://schema.org/InStock" if product.stock_quantity > 0 and product.is_available else "https://schema.org/OutOfStock",
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {"@type": "Organization", "name": "Nismita Craft Studio"},
        },
    }
    ctx = {
        "product": product,
        "related": related,
        "shipping": settings.SHIPPING_FLAT,
        "product_seo_schema": product_seo_schema,
    }
    ctx.update(_nav(request))
    return render(request, "storefront/detail.html", ctx)


@login_required
def wishlist(request):
    g = _staff_guard(request)
    if g:
        return g
    wl, _ = Wishlist.objects.get_or_create(user=request.user)
    items = [i.product for i in wl.items.select_related("product", "product__category")]
    ctx = {"title": "My Wishlist", "subtitle": f"{len(items)} saved items", "body": "", "items": items}
    ctx.update(_nav(request))
    return render(request, "storefront/page.html", ctx)


@login_required
def wishlist_add(request, pk):
    wl, _ = Wishlist.objects.get_or_create(user=request.user)
    product = get_object_or_404(Product, pk=pk, is_active=True)
    _, created = WishlistItem.objects.get_or_create(wishlist=wl, product=product)
    messages.success(request, f"{'Added' if created else 'Already in wishlist'}: {product.name}")
    return redirect("storefront:detail", slug=product.slug)


def login_view(request):
    if request.user.is_authenticated:
        nxt = request.GET.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        # Admins land on the owner dashboard, customers on the storefront.
        if request.user.is_staff:
            return redirect("storefront:dashboard")
        return redirect("storefront:home")
    ctx = {"next": request.GET.get("next", "") or request.POST.get("next", "")}
    ctx.update(_nav(request))
    if request.method == "POST":
        ident = (request.POST.get("username") or "").strip()
        # Allow login with username OR email (professional UX).
        try:
            user_obj = User.objects.filter(username__iexact=ident).first() or User.objects.filter(email__iexact=ident).first()
            username = user_obj.username if user_obj else ident
        except Exception:
            username = ident
        user = authenticate(request, username=username, password=request.POST.get("password"))
        if user is not None:
            login(request, user)
            if not request.POST.get("remember"):
                request.session.set_expiry(0)
            _merge_session_cart(request)
            messages.success(request, f"Welcome back, {user.username}!")
            nxt = request.POST.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            # Admins land on the owner dashboard, customers on the storefront.
            if user.is_staff:
                return redirect("storefront:dashboard")
            return redirect("storefront:home")
        messages.error(request, "Invalid username/email or password. Please try again.")
    return render(request, "storefront/login.html", ctx)


def register_view(request):
    if request.user.is_authenticated:
        return redirect("storefront:home")
    ctx = {}
    ctx.update(_nav(request))
    if request.method == "POST":
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        if not username or not email or not password:
            messages.error(request, "Username, email and password are required.")
        elif password != password2:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already taken. Try another one.")
        elif User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already registered. Try signing in instead.")
        else:
            try:
                validate_password(password)
            except DjangoValidationError as e:
                messages.error(request, " ".join(e.messages))
                return render(request, "storefront/register.html", ctx)
            user = User.objects.create_user(username=username, email=email, password=password, role=User.Roles.CUSTOMER)
            login(request, user)
            _merge_session_cart(request)
            messages.success(request, f"Account created. Welcome, {username}!")
            return redirect("storefront:home")
    return render(request, "storefront/register.html", ctx)


def logout_view(request):
    logout(request)
    messages.success(request, "Signed out.")
    return redirect("storefront:home")


def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    try:
        qty = max(1, int(request.POST.get("quantity", 1) or 1))
    except (TypeError, ValueError):
        qty = 1
    variant = None
    if request.POST.get("variant"):
        variant = get_object_or_404(ProductVariant, pk=request.POST["variant"], product=product, is_active=True)
    available = (variant.stock_quantity if variant else product.stock_quantity) or 0
    if available <= 0:
        messages.error(request, f"{product.name} is out of stock.")
        return redirect(request.META.get("HTTP_REFERER") or f"/product/{product.slug}/")
    qty = min(qty, available)  # never hold more than exists in stock
    if not request.user.is_authenticated:
        items = _session_cart(request)
        for entry in items:
            if entry["product"] == product.id and entry.get("variant") == (variant.id if variant else None):
                entry["quantity"] += qty
                break
        else:
            items.append({"product": product.id, "variant": variant.id if variant else None, "quantity": qty})
        _save_session_cart(request, items)
        messages.info(request, "Please sign in to add items to your cart and buy.")
        return redirect(f"/login/?next=/product/{product.slug}/")
    cart = _get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, variant=variant, defaults={"quantity": qty})
    if not created:
        item.quantity += qty
        item.save(update_fields=["quantity", "updated_at"])
    messages.success(request, f"Added to cart: {product.name}")
    return redirect("storefront:cart")
@login_required
def cart_view(request):
    g = _staff_guard(request)
    if g:
        return g
    cart = _get_or_create_cart(request)
    items = list(
        cart.items.select_related("product", "product__category", "variant").prefetch_related("product__images")
    )
    subtotal = cart.subtotal
    shipping = _shipping_for()
    ctx = {
        "cart": cart,
        "items": items,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": subtotal + shipping,
    }
    ctx.update(_nav(request))
    return render(request, "storefront/cart.html", ctx)


@login_required
def cart_update(request, pk):
    cart = _get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=pk, cart=cart)
    qty = int(request.POST.get("quantity", 1))
    if qty <= 0:
        item.delete()
    else:
        item.quantity = qty
        item.save(update_fields=["quantity", "updated_at"])
    return redirect("storefront:cart")


@login_required
def cart_remove(request, pk):
    cart = _get_or_create_cart(request)
    CartItem.objects.filter(pk=pk, cart=cart).delete()
    return redirect("storefront:cart")


def _shipping_for():
    return settings.SHIPPING_FLAT


def _whatsapp_url(order):
    lines = [
        "Namaste Nismita Craft Studio 🕯️",
        f"Order: {order.order_number}",
        f"Amount: Rs {order.total}",
        f"Payment: {order.get_payment_method_display()}"
        + (f" (Ref: {order.payment_reference})" if order.payment_reference else ""),
        f"Name: {order.full_name} — {order.phone}",
        f"Address: {order.city}, {order.district}, {order.province}",
        "Items:",
    ]
    lines += [f"• {i.quantity} x {i.product_name} — Rs {i.total_price}" for i in order.items.all()]
    lines.append("Payment screenshot attached 🙏 Please confirm my order.")
    return f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={quote(chr(10).join(lines))}"


def _start_esewa_payment(request, order_num):
    """Return (mode, payload) for eSewa ePay v2 when the gateway is configured.

    ePay v2 requires a browser form POST with a signed payload, so the primary
    mode is ``"form"`` — an auto-submitting HTML form the checkout template
    renders directly.  Returns ``(None, None)`` (the order stays on the manual
    WhatsApp flow) when merchant credentials are missing or eSewa errors.
    """
    gateway = get_gateway(Order.PaymentMethod.ESEWA)
    if not gateway_ready(gateway):
        return None, None
    try:
        order = Order.objects.get(order_number=order_num)
        callback = request.build_absolute_uri(reverse("storefront:esewa-callback"))
        form_html = gateway.get_initiate_form(order, callback)
        return "form", form_html
    except Exception as exc:  # noqa: BLE001 — always fall back to manual payment
        logger.warning("eSewa initiate failed for %s: %s", order_num, exc)
        messages.warning(
            request,
            "eSewa online payment is unavailable right now — your order is saved; "
            "you can pay manually and send the screenshot on WhatsApp.",
        )
        return None, None


@login_required
def checkout(request):
    g = _staff_guard(request)
    if g:
        return g
    cart = _get_or_create_cart(request)
    items = list(cart.items.select_related("product", "product__seller", "variant").prefetch_related("product__images"))
    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect("storefront:cart")

    shipping = _shipping_for()
    total = cart.subtotal + shipping
    ctx = {
        "items": items,
        "subtotal": cart.subtotal,
        "shipping": shipping,
        "total": total,
        "addresses": Address.objects.filter(user=request.user),
        "provinces": PROVINCE_CHOICES,
        "districts_json": json.dumps(PROVINCES, ensure_ascii=False),
    }
    ctx.update(_nav(request))

    if request.method == "POST":
        data = request.POST
        province = data.get("province", "")
        district = data.get("district", "")
        payment_method = data.get("payment_method", "")
        errors = []

        if province not in PROVINCES:
            errors.append("Select a valid province.")
        elif district not in PROVINCES[province]:
            errors.append("Select a valid district.")
        if payment_method not in Order.PaymentMethod.values:
            errors.append("Choose a payment method.")
        if not data.get("full_name", "").strip():
            errors.append("Full name is required.")
        if not data.get("phone", "").strip():
            errors.append("Phone number is required.")
        if not data.get("address_line", "").strip():
            errors.append("Street address is required.")

        # --- Validate payment screenshot before touching stock ---
        screenshot = request.FILES.get("payment_screenshot")
        if screenshot:
            try:
                validate_payment_screenshot(screenshot)
            except DjangoValidationError as e:
                errors.append(" ".join(e.messages) if isinstance(e.messages, list) else str(e))

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "storefront/checkout.html", ctx)

        order_num = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        try:
            place_order_from_cart(
                cart=cart,
                cart_items=items,
                customer=request.user,
                order_num=order_num,
                shipping_cost=shipping,
                payment_method=payment_method,
                payment_reference=data.get("payment_reference", "").strip(),
                whatsapp_number=data.get("whatsapp_number", "").strip(),
                full_name=data.get("full_name", "").strip(),
                phone=data.get("phone", "").strip(),
                province=province,
                district=district,
                city=data.get("city", "").strip(),
                address_line=data.get("address_line", "").strip(),
                landmark=data.get("landmark", "").strip(),
            )
        except InsufficientStock as exc:
            messages.error(request, str(exc))
            return render(request, "storefront/checkout.html", ctx)

        # Attach screenshot after a successful stock reservation + order write.
        if screenshot:
            order = Order.objects.get(order_number=order_num)
            order.payment_screenshot = screenshot
            order.save(update_fields=["payment_screenshot", "updated_at"])

        # eSewa online payment: render the auto-submitting ePay v2 form when the
        # gateway is configured; otherwise fall through to the manual WhatsApp flow.
        if payment_method == Order.PaymentMethod.ESEWA:
            pay_mode, pay_payload = _start_esewa_payment(request, order_num)
            if pay_mode == "form":
                return render(request, "storefront/esewa_redirect.html", {
                    "esewa_form": pay_payload,
                    "order_number": order_num,
                    "total": total,
                })

        messages.success(
            request, f"Order placed: {order_num} — send your payment screenshot on WhatsApp."
        )
        return redirect("storefront:order-success", number=order_num)

    return render(request, "storefront/checkout.html", ctx)


@login_required
def order_success(request, number):
    order = get_object_or_404(Order, order_number=number, customer=request.user)
    if request.method == "POST" and request.FILES.get("payment_screenshot"):
        screenshot = request.FILES["payment_screenshot"]
        try:
            validate_payment_screenshot(screenshot)
        except DjangoValidationError as e:
            msg = " ".join(e.messages) if isinstance(e.messages, list) else str(e)
            messages.error(request, msg)
            return redirect("storefront:order-success", number=order.order_number)
        order.payment_screenshot = screenshot
        order.save(update_fields=["payment_screenshot", "updated_at"])
        messages.success(request, "Screenshot uploaded — also send it on WhatsApp for fastest confirmation.")
        return redirect("storefront:order-success", number=order.order_number)
    ctx = {
        "order": order,
        "wa_url": _whatsapp_url(order),
    }
    ctx.update(_nav(request))
    return render(request, "storefront/order_success.html", ctx)


@login_required
def orders_view(request):
    g = _staff_guard(request)
    if g:
        return g
    qs = (
        Order.objects.filter(customer=request.user)
        .prefetch_related("items__product__images")
        .order_by("-created_at")
    )
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    ctx = {"orders": page, "page_obj": page}
    ctx.update(_nav(request))
    return render(request, "storefront/orders.html", ctx)




def about(request):
    ctx = {"title": "About Us", "subtitle": "Nismita Craft Studio", "items": [],
           "body": "<p>We supply premium candle-making materials — wax, wicks, silicone molds, colours & glitters — curated for makers, inspired by ukiyointernational.com.</p>"}
    ctx.update(_nav(request))
    return render(request, "storefront/page.html", ctx)


def contact(request):
    ctx = {"title": "Contact Us", "subtitle": "We reply within 1 business day", "items": [],
           "body": (
               "<p><b>Address:</b> Narephate - 32, Kathmandu<br>"
               "<b>Phone:</b> <a href=\"tel:+9779708909514\">+977 970-8909514</a><br>"
               "<b>WhatsApp:</b> <a href=\"https://wa.me/9779708909514\" target=\"_blank\" rel=\"noopener\">Chat with us on WhatsApp</a></p>"
           )}
    ctx.update(_nav(request))
    return render(request, "storefront/page.html", ctx)


# ---------------------------------------------------------------------------
# eSewa callback — eSewa redirects here after the customer pays; verify the
# signature remotely and mark the order's payment verified + confirmed.
# ---------------------------------------------------------------------------
@csrf_exempt
def esewa_callback(request):
    params = {**request.POST.dict(), **request.GET.dict()}
    tid = params.get("transaction_id") or params.get("tid") or ""
    order = Order.objects.filter(order_number=tid).first()
    if order is None:
        messages.error(request, "eSewa callback referenced an unknown order.")
        return redirect("storefront:home")

    if order.payment_status == Order.PaymentStatus.VERIFIED:
        messages.info(request, f"Payment for {order.order_number} was already verified.")
        return redirect("storefront:order-success", number=order.order_number)

    gateway = get_gateway(Order.PaymentMethod.ESEWA)
    if not gateway_ready(gateway):
        messages.error(request, "eSewa is not configured on the server.")
        return redirect("storefront:order-success", number=order.order_number)

    result = gateway.verify(params)

    # Never accept an underpayment: the signed amount must cover the total.
    amount_due = int(order.total * 100)  # NPR -> paisa
    if result.ok and result.amount is not None and result.amount < amount_due:
        result = TransactionResult(
            ok=False,
            error=f"Amount mismatch: received {result.amount} paisa, due {amount_due} paisa",
        )

    if result.ok:
        with transaction.atomic():
            order.payment_status = Order.PaymentStatus.VERIFIED
            order.payment_reference = order.payment_reference or tid or order.order_number
            if order.status == Order.Status.PENDING:
                order.status = Order.Status.CONFIRMED
                order.confirmed_at = timezone.now()
            order.save(
                update_fields=["payment_status", "payment_reference", "status", "confirmed_at", "updated_at"]
            )
        logger.info("eSewa payment verified for %s (tid=%s)", order.order_number, tid)
        messages.success(request, f"Payment verified for {order.order_number} — order confirmed 🎉")
    else:
        logger.warning("eSewa callback rejected for %s: %s", order.order_number, result.error)
        messages.error(
            request,
            f"eSewa payment could not be verified: {result.error or result.status or 'unknown error'}",
        )
    return redirect("storefront:order-success", number=order.order_number)

