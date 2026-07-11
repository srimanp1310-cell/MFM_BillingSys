from flask import render_template, request
from flask_login import login_required

from app.extensions import db
from app.models import Category, Product
from app.stock import bp


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
