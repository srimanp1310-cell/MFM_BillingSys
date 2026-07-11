from decimal import Decimal, InvalidOperation

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Brand, Category, Product, PurchaseInvoice
from app.purchases import bp
from app.purchases.forms import PurchaseHeaderForm
from app.services import product_service, stock_service
from app.utils import local_now


def _active_products_payload():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return [
        {
            "id": p.id,
            "label": f"{p.code} — {p.display_name}",
            "cost": str(p.cost_price) if p.cost_price is not None else "",
            "price": str(p.unit_price),
            "on_hand": p.quantity_on_hand,
        }
        for p in products
    ]


def _categories_payload():
    cats = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()
    return (
        [{"id": c.id, "name": c.name, "track_size": c.track_size} for c in cats],
        [{"id": b.id, "name": b.name, "category_id": b.category_id} for b in brands],
    )


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    query = PurchaseInvoice.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                PurchaseInvoice.supplier_name.ilike(like),
                PurchaseInvoice.supplier_invoice_number.ilike(like),
            )
        )
    invoices = query.order_by(PurchaseInvoice.created_at.desc()).limit(200).all()
    return render_template("purchases/index.html", invoices=invoices, q=q)


@bp.route("/<int:invoice_id>")
@login_required
def detail(invoice_id):
    invoice = db.get_or_404(PurchaseInvoice, invoice_id)
    return render_template("purchases/detail.html", invoice=invoice)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = PurchaseHeaderForm(purchase_date=local_now().date())
    if form.validate_on_submit():
        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("quantity[]")
        unit_costs = request.form.getlist("unit_cost[]")
        lines = []
        try:
            for pid, qty, cost in zip(product_ids, quantities, unit_costs):
                if not pid:
                    continue
                product = db.session.get(Product, int(pid))
                if product is None:
                    raise ValueError("Unknown product in line items.")
                try:
                    unit_cost = Decimal(cost) if cost.strip() else None
                except InvalidOperation:
                    raise ValueError(f"Invalid cost '{cost}' for {product.name}.")
                lines.append({"product": product, "quantity": int(qty or 0), "unit_cost": unit_cost})

            invoice = stock_service.create_purchase(
                {
                    "supplier_name": form.supplier_name.data.strip(),
                    "supplier_invoice_number": form.supplier_invoice_number.data.strip(),
                    "purchase_date": form.purchase_date.data,
                    "note": (form.note.data or "").strip() or None,
                },
                lines,
                current_user.id,
            )
            flash(
                f"Stock entry saved against invoice '{invoice.supplier_invoice_number}' — "
                f"{len(lines)} line{'s' if len(lines) != 1 else ''} added to stock.",
                "success",
            )
            return redirect(url_for("purchases.detail", invoice_id=invoice.id))
        except (ValueError, InvalidOperation) as e:
            flash(str(e), "danger")

    categories, brands = _categories_payload()
    return render_template(
        "purchases/form.html",
        form=form,
        products=_active_products_payload(),
        categories=categories,
        brands=brands,
    )


@bp.route("/api/products", methods=["POST"])
@login_required
def api_create_product():
    """Inline product creation from the stock-entry and billing screens."""
    data = request.get_json(silent=True) or {}
    try:
        if (data.get("new_category_name") or "").strip():
            category = product_service.get_or_create_category(
                data["new_category_name"], bool(data.get("new_category_track_size"))
            )
        else:
            category = db.session.get(Category, int(data.get("category_id") or 0))
            if category is None:
                raise ValueError("Pick a category or type a new one.")

        brand = None
        if (data.get("new_brand_name") or "").strip():
            brand = product_service.get_or_create_brand(data["new_brand_name"], category)
        elif data.get("brand_id"):
            brand = db.session.get(Brand, int(data["brand_id"]))
            if brand and brand.category_id != category.id:
                raise ValueError("That brand belongs to a different category.")

        if not (data.get("name") or "").strip():
            raise ValueError("Product name is required.")
        try:
            unit_price = Decimal(str(data.get("unit_price") or "0"))
        except InvalidOperation:
            raise ValueError("Invalid selling price.")

        track_size = category.track_size or bool(data.get("new_category_track_size"))
        reorder_level = str(data.get("reorder_level") or "").strip()
        product = product_service.create_product(
            name=data["name"],
            category=category,
            brand=brand,
            code=data.get("code"),
            size=data.get("size") if track_size else None,
            unit=data.get("unit") or "piece",
            unit_price=unit_price,
            reorder_level=int(reorder_level) if reorder_level else None,
            hsn_code=data.get("hsn_code"),
        )
        db.session.commit()
        return jsonify(
            {
                "ok": True,
                "product": {
                    "id": product.id,
                    "label": f"{product.code} — {product.display_name}",
                    "cost": "",
                    "price": str(product.unit_price),
                    "on_hand": 0,
                },
            }
        )
    except (ValueError, InvalidOperation) as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
