"""Category/brand/product creation helpers shared by admin CRUD and the
inline "new product" flow in Stock Entry. No commits here — callers own the
transaction."""

import re

from app.extensions import db
from app.models import Brand, Category, Product


def get_or_create_category(name, track_size=False):
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty.")
    existing = Category.query.filter(db.func.lower(Category.name) == name.lower()).first()
    if existing:
        return existing
    category = Category(name=name, track_size=track_size)
    db.session.add(category)
    db.session.flush()
    return category


def get_or_create_brand(name, category):
    name = name.strip()
    if not name:
        raise ValueError("Brand name cannot be empty.")
    existing = Brand.query.filter(
        db.func.lower(Brand.name) == name.lower(), Brand.category_id == category.id
    ).first()
    if existing:
        return existing
    brand = Brand(name=name, category_id=category.id)
    db.session.add(brand)
    db.session.flush()
    return brand


def generate_product_code(category):
    """Readable unique code like CHA-001 from the category name."""
    prefix = re.sub(r"[^A-Za-z]", "", category.name).upper()[:3] or "PRD"
    count = Product.query.filter(Product.code.like(f"{prefix}-%")).count()
    while True:
        count += 1
        code = f"{prefix}-{count:03d}"
        if not Product.query.filter_by(code=code).first():
            return code


def create_product(
    name,
    category,
    brand=None,
    code=None,
    size=None,
    unit="piece",
    unit_price=0,
    cost_price=None,
    reorder_level=None,
    description=None,
    hsn_code=None,
):
    code = (code or "").strip() or generate_product_code(category)
    if Product.query.filter(db.func.lower(Product.code) == code.lower()).first():
        raise ValueError(f"Product code '{code}' already exists.")
    product = Product(
        code=code,
        name=name.strip(),
        category_id=category.id,
        brand_id=brand.id if brand else None,
        size=(size or "").strip() or None,
        hsn_code=(hsn_code or "").strip() or None,
        unit=unit or "piece",
        unit_price=unit_price,
        cost_price=cost_price,
        reorder_level=reorder_level,
        description=(description or "").strip() or None,
    )
    db.session.add(product)
    db.session.flush()
    return product
