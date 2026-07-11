from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.billing import bp
from app.extensions import db
from app.models import PAYMENT_METHODS, AppSetting, Bill, Product
from app.services import billing_service, notify_service
from app.utils import local_now

TWO_PLACES = Decimal("0.01")


def _products_payload():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return [
        {
            "id": p.id,
            "label": f"{p.code} — {p.display_name}",
            "price": str(p.unit_price),
            "on_hand": p.quantity_on_hand,
        }
        for p in products
    ]


@bp.route("/")
@login_required
def index():
    from app.models import Brand, Category

    categories = [
        {"id": c.id, "name": c.name, "track_size": c.track_size}
        for c in Category.query.filter_by(is_active=True).order_by(Category.name)
    ]
    brands = [
        {"id": b.id, "name": b.name, "category_id": b.category_id}
        for b in Brand.query.filter_by(is_active=True).order_by(Brand.name)
    ]
    next_number_hint = f"INV-{local_now().year}-…"
    return render_template(
        "billing/index.html",
        products=_products_payload(),
        categories=categories,
        brands=brands,
        payment_methods=PAYMENT_METHODS,
        next_number_hint=next_number_hint,
    )


def _parse_decimal(raw, field, default=Decimal("0")):
    raw = (raw or "").strip()
    if not raw:
        return default
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"Invalid {field}: '{raw}'")
    if value < 0:
        raise ValueError(f"{field.capitalize()} cannot be negative.")
    return value


@bp.route("/save", methods=["POST"])
@login_required
def save():
    try:
        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("quantity[]")
        unit_prices = request.form.getlist("unit_price[]")

        lines = []
        subtotal = Decimal("0")
        for pid, qty, price in zip(product_ids, quantities, unit_prices):
            if not pid:
                continue
            product = db.session.get(Product, int(pid))
            if product is None:
                raise ValueError("Unknown product in line items.")
            unit_price = _parse_decimal(price, "price", None)
            if unit_price is None:
                unit_price = product.unit_price
            qty = int(qty or 0)
            lines.append({"product": product, "quantity": qty, "unit_price": unit_price})
            subtotal += unit_price * qty

        discount = _parse_decimal(request.form.get("discount"), "discount")

        tax_amount = Decimal("0")
        if request.form.get("apply_tax") == "1":
            tax_value = _parse_decimal(request.form.get("tax_value"), "tax")
            if request.form.get("tax_mode") == "percent":
                tax_amount = ((subtotal - discount) * tax_value / 100).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
            else:
                tax_amount = tax_value

        payment_method = request.form.get("payment_method", "cash")
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Invalid payment method.")

        bill = billing_service.create_bill(
            {
                "bill_number": request.form.get("bill_number", ""),
                "customer_name": (request.form.get("customer_name") or "").strip(),
                "customer_phone": (request.form.get("customer_phone") or "").strip(),
                "discount": discount,
                "tax_amount": tax_amount,
                "payment_method": payment_method,
            },
            lines,
            current_user.id,
        )

        low = [line["product"] for line in lines if line["product"].is_low_stock]
        notify_service.notify_low_stock(low)

        flash(f"Bill {bill.bill_number} saved.", "success")
        return redirect(url_for("billing.view", bill_id=bill.id))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("billing.index"))


@bp.route("/bill/<int:bill_id>")
@login_required
def view(bill_id):
    bill = db.get_or_404(Bill, bill_id)
    return render_template("billing/bill.html", bill=bill, shop=AppSetting.all_settings())
