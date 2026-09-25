"""Storefront URLs (public HTML, Ukiyo-style)."""
from django.urls import path
from django.views.generic import RedirectView

from . import dashboard, views

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("shop/", views.shop, name="shop"),
    path("category/<slug:slug>/", views.shop, name="category"),
    path("product/<slug:slug>/", views.detail, name="detail"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("customer-preview/start/", views.start_customer_preview, name="customer-preview-start"),
    path("customer-preview/return/", views.return_from_customer_preview, name="customer-preview-return"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.cart_add, name="cart-add"),
    path("cart/update/<int:pk>/", views.cart_update, name="cart-update"),
    path("cart/remove/<int:pk>/", views.cart_remove, name="cart-remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.orders_view, name="orders"),
    path("orders/<str:number>/", views.order_success, name="order-success"),
    path("payment/esewa/callback/", views.esewa_callback, name="esewa-callback"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/add/<int:pk>/", views.wishlist_add, name="wishlist-add"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("dashboard/", dashboard.dashboard_home, name="dashboard"),
    path("dashboard/product/add/", dashboard.dashboard_add_product, name="dashboard-add-product"),
    path("dashboard/products/", dashboard.dashboard_products, name="dashboard-products"),
    path("dashboard/report/", dashboard.dashboard_report, name="dashboard-report"),
    path("dashboard/sales/", RedirectView.as_view(url="/dashboard/report/", permanent=False), name="dashboard-sales"),
    path("dashboard/orders/", dashboard.dashboard_orders, name="dashboard-orders"),
    path("dashboard/order/<int:pk>/", dashboard.dashboard_order, name="dashboard-order"),
]
