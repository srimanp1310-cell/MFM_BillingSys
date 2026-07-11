from flask import flash, redirect, render_template, request, url_for

from app.admin import bp
from app.admin.forms import NEW_SENTINEL, BrandForm, CategoryForm, ProductForm, SettingsForm
from app.extensions import db
from app.models import AppSetting, Brand, Category, Product
from app.services import product_service, stock_service
from app.utils import admin_required


@bp.route("/")
@admin_required
def index():
    return render_template("admin/index.html")


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    form = SettingsForm(data=AppSetting.all_settings())
    if form.validate_on_submit():
        for key in AppSetting.DEFAULTS:
            AppSetting.set(key, (getattr(form, key).data or "").strip())
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", form=form)


@bp.route("/recompute", methods=["POST"])
@admin_required
def recompute():
    drifted = stock_service.recompute_from_ledger()
    if not drifted:
        flash("Stock check passed — all quantities match the ledger.", "success")
    else:
        details = "; ".join(
            f"{d['product'].name}: {d['cached']} → {d['ledger']}" for d in drifted
        )
        flash(f"Fixed {len(drifted)} drifted product(s): {details}", "warning")
    return redirect(url_for("admin.index"))


# --- categories & brands ---


@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    cat_form = CategoryForm()
    brand_form = BrandForm()
    brand_form.category_id.choices = [
        (c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name)
    ]
    if cat_form.submit.data and cat_form.validate_on_submit():
        try:
            product_service.get_or_create_category(cat_form.name.data, cat_form.track_size.data)
            db.session.commit()
            flash("Category saved.", "success")
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
        return redirect(url_for("admin.categories"))
    all_categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin/categories.html", categories=all_categories, cat_form=cat_form, brand_form=brand_form
    )


@bp.route("/brands/new", methods=["POST"])
@admin_required
def create_brand():
    form = BrandForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name)]
    if form.validate_on_submit():
        category = db.get_or_404(Category, form.category_id.data)
        try:
            product_service.get_or_create_brand(form.name.data, category)
            db.session.commit()
            flash("Brand saved.", "success")
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
    return redirect(url_for("admin.categories"))


@bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@admin_required
def toggle_category(category_id):
    category = db.get_or_404(Category, category_id)
    category.is_active = not category.is_active
    db.session.commit()
    flash(f"Category '{category.name}' {'activated' if category.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.categories"))


@bp.route("/brands/<int:brand_id>/toggle", methods=["POST"])
@admin_required
def toggle_brand(brand_id):
    brand = db.get_or_404(Brand, brand_id)
    brand.is_active = not brand.is_active
    db.session.commit()
    flash(f"Brand '{brand.name}' {'activated' if brand.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.categories"))


# --- products ---


@bp.route("/products")
@admin_required
def products():
    q = request.args.get("q", "").strip()
    include_inactive = request.args.get("all") == "1"
    query = Product.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.code.ilike(like)))
    items = query.order_by(Product.name).all()
    return render_template("admin/products.html", products=items, q=q, include_inactive=include_inactive)


def _resolve_category_brand(form):
    """Turn the form's select/new fields into Category and Brand rows."""
    if form.category_id.data == NEW_SENTINEL:
        category = product_service.get_or_create_category(
            form.new_category_name.data or "", form.new_category_track_size.data
        )
    else:
        category = db.get_or_404(Category, form.category_id.data)

    brand = None
    if form.brand_id.data == NEW_SENTINEL:
        brand = product_service.get_or_create_brand(form.new_brand_name.data or "", category)
    elif form.brand_id.data:
        brand = db.get_or_404(Brand, form.brand_id.data)
        if brand.category_id != category.id:
            raise ValueError(f"Brand '{brand.name}' belongs to a different category.")
    return category, brand


@bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def new_product():
    form = ProductForm()
    form.set_choices()
    if form.validate_on_submit():
        try:
            category, brand = _resolve_category_brand(form)
            product = product_service.create_product(
                name=form.name.data,
                category=category,
                brand=brand,
                code=form.code.data,
                size=form.size.data if (category.track_size or form.new_category_track_size.data) else None,
                unit=form.unit.data,
                unit_price=form.unit_price.data,
                cost_price=form.cost_price.data,
                reorder_level=form.reorder_level.data,
                description=form.description.data,
                hsn_code=form.hsn_code.data,
            )
            db.session.commit()
            flash(f"Product '{product.display_name}' created (code {product.code}).", "success")
            return redirect(url_for("admin.products"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
    return render_template("admin/product_form.html", form=form, product=None)


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    product = db.get_or_404(Product, product_id)
    form = ProductForm(obj=product)
    form.set_choices()
    if form.validate_on_submit():
        try:
            category, brand = _resolve_category_brand(form)
            code = (form.code.data or "").strip() or product.code
            clash = Product.query.filter(
                db.func.lower(Product.code) == code.lower(), Product.id != product.id
            ).first()
            if clash:
                raise ValueError(f"Product code '{code}' already exists.")
            product.code = code
            product.name = form.name.data.strip()
            product.category_id = category.id
            product.brand_id = brand.id if brand else None
            product.size = (form.size.data or "").strip() or None
            if not category.track_size:
                product.size = None
            product.hsn_code = (form.hsn_code.data or "").strip() or None
            product.unit = form.unit.data
            product.unit_price = form.unit_price.data
            product.cost_price = form.cost_price.data
            product.reorder_level = form.reorder_level.data
            product.description = (form.description.data or "").strip() or None
            db.session.commit()
            flash(f"Product '{product.display_name}' updated.", "success")
            return redirect(url_for("admin.products"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
    return render_template("admin/product_form.html", form=form, product=product)


@bp.route("/products/<int:product_id>/toggle", methods=["POST"])
@admin_required
def toggle_product(product_id):
    product = db.get_or_404(Product, product_id)
    product.is_active = not product.is_active
    db.session.commit()
    flash(f"Product '{product.name}' {'activated' if product.is_active else 'deactivated'}.", "success")
    return redirect(request.referrer or url_for("admin.products"))
