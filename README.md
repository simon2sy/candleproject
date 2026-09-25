# Candle Ecommerce — Phase 1 Backend (Django + DRF)

Multi-seller / multi-buyer marketplace for candle-making supplies
(molds, wax, wicks, colours, glitter, tools).

## Stack
- Django 6.1, Django REST Framework, SimpleJWT, django-filter
- PostgreSQL in production (`DATABASE_URL`), SQLite fallback for local dev
- Pillow (product/category/seller images), django-cors-headers, python-dotenv

## Why each dependency
| Package | Why |
|---|---|
| `Django` | Web framework + ORM + Admin |
| `djangorestframework` | REST APIs (`/api/v1/...`) |
| `djangorestframework-simplejwt` | JWT login/refresh (`/api/v1/auth/...`) |
| `django-filter` | `?category=&min_price=&max_price=&search=&ordering=` |
| `psycopg[binary]` | PostgreSQL driver (production DB) |
| `Pillow` | `ImageField` uploads |
| `django-cors-headers` | Allow React frontend origin later |
| `python-dotenv` | Load `.env` (secrets never committed) |

## Setup (Windows PowerShell)
```powershell
mkdir ecommerce; cd ecommerce
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install django djangorestframework djangorestframework-simplejwt django-filter "psycopg[binary]" pillow django-cors-headers python-dotenv
pip freeze > requirements.txt
django-admin startproject config .
python manage.py startapp accounts
python manage.py startapp catalog
python manage.py startapp orders
copy .env.example .env   # then edit SECRET_KEY / DATABASE_URL
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

PostgreSQL production example:
```text
DATABASE_URL=postgres://candle_user:candle_pass@localhost:5432/candle_ecommerce
```

## API (all under /api/v1/)
- Auth: `POST auth/register/`, `POST auth/login/`, `POST auth/token/refresh/`, `GET/PATCH auth/me/`
- Catalog (public read): `GET categories/`, `GET products/?category=silicone-molds&min_price=100&max_price=900&search=wax&ordering=price`, `GET products/<slug>/`, `GET variants/`
- Seller (approved only): `POST/PATCH/DELETE products/`, `POST/PATCH variants/`
- Customer: `GET/POST/PATCH/DELETE addresses/`, `GET wishlist/`, `POST wishlist/add/`, `POST wishlist/remove/`, `GET/POST orders/`

## Roles & rules
- Registration only allows `CUSTOMER` or `SELLER`; `ADMIN` is rejected (400).
- Sellers get an auto-created `SellerProfile`, `is_seller_approved=False` until admin approves (`/admin/` → Users → Approve).
- Unapproved sellers get 403 on product creation. Seller A cannot edit Seller B's product (403). Customers only see their own addresses/orders.

## Admin (/admin/)
Users (approve/unapprove actions), SellerProfiles (verify), Addresses, Categories, Products (+variant/image/attribute inlines), InventoryLog, Wishlists, Orders (+items inline, status filter).

## Tests
```powershell
python manage.py test tests -v 2
```
Covers: customer registration, ADMIN-block, seller auto-profile, approval gate, seller A vs B isolation, address privacy + single-default, wishlist uniqueness, order price snapshots.
