from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Category, Product, StockMovement
from app.services import stock_service
from app.stock import bp
from app.utils import admin_required


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    low_only = request.args.get("low") == "1"
    include_inactive = request.args.get("all") == "1"

    query = Product.query
    if not include_inactive:
        query = query.filter(Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.code.ilike(like)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if low_only:
        query = query.filter(
            Product.reorder_level.isnot(None), Product.quantity_on_hand <= Product.reorder_level
        )

    products = query.order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    low_count = sum(1 for p in products if p.is_low_stock) if not low_only else len(products)
    return render_template(
        "stock/index.html",
        products=products,
        categories=categories,
        q=q,
        category_id=category_id,
        low_only=low_only,
        include_inactive=include_inactive,
        low_count=low_count,
    )


@bp.route("/<int:product_id>/adjust", methods=["POST"])
@admin_required
def adjust(product_id):
    product = db.get_or_404(Product, product_id)
    delta = request.form.get("delta", type=int)
    note = request.form.get("note", "")
    try:
        if delta is None:
            raise ValueError("Enter a quantity change (e.g. -2 or 5).")
        stock_service.adjust_stock(product, delta, note, current_user.id)
        flash(
            f"Stock adjusted: {product.name} {'+' if delta > 0 else ''}{delta} → now {product.quantity_on_hand}.",
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("stock.index"))


@bp.route("/<int:product_id>/movements")
@login_required
def movements(product_id):
    product = db.get_or_404(Product, product_id)
    items = (
        StockMovement.query.filter_by(product_id=product_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(300)
        .all()
    )
    return render_template("stock/movements.html", product=product, movements=items)
