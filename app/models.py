"""All SQLAlchemy models.

Money is Numeric/Decimal, never float. Stock truth lives in the StockMovement
ledger; Product.quantity_on_hand is a cache that must always equal the ledger
sum (see stock_service.recompute).
"""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    """Naive UTC timestamp (SQLite-friendly; converted to local tz on display)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- constants (kept as plain strings for portability across SQLite/Postgres) ---

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"

MOVE_SALE = "SALE"
MOVE_PURCHASE = "PURCHASE"
MOVE_RETURN = "RETURN"
MOVE_ADJUSTMENT = "ADJUSTMENT"
MOVE_VOID_REVERSAL = "VOID_REVERSAL"

BILL_COMPLETED = "completed"
BILL_VOIDED = "voided"

PAYMENT_METHODS = ["cash", "card", "other"]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default=ROLE_STAFF)
    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_active(self):  # consumed by Flask-Login
        return self.is_active_flag


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    # Whether products in this category carry a size (mattresses yes, chairs no).
    track_size = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    brands = db.relationship("Brand", backref="category", lazy="dynamic")
    products = db.relationship("Product", backref="category", lazy="dynamic")


class Brand(db.Model):
    __tablename__ = "brands"
    __table_args__ = (db.UniqueConstraint("name", "category_id"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship("Product", backref="brand", lazy="dynamic")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"))
    size = db.Column(db.String(64))  # only meaningful when category.track_size
    description = db.Column(db.Text)
    unit = db.Column(db.String(16), nullable=False, default="piece")
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cost_price = db.Column(db.Numeric(12, 2))
    quantity_on_hand = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    movements = db.relationship("StockMovement", backref="product", lazy="dynamic")

    @property
    def display_name(self):
        parts = [self.name]
        if self.brand:
            parts.append(f"[{self.brand.name}]")
        if self.size:
            parts.append(f"({self.size})")
        return " ".join(parts)

    @property
    def is_low_stock(self):
        return self.reorder_level is not None and self.quantity_on_hand <= self.reorder_level


class StockMovement(db.Model):
    """Audit ledger — the source of truth for stock."""

    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    change_qty = db.Column(db.Integer, nullable=False)
    movement_type = db.Column(db.String(16), nullable=False)
    reference_type = db.Column(db.String(16))  # "bill" | "purchase"
    reference_id = db.Column(db.Integer)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    creator = db.relationship("User")


class BillSequence(db.Model):
    """One row per year; last_number is bumped under a row lock for gap-free numbering."""

    __tablename__ = "bill_sequences"

    year = db.Column(db.Integer, primary_key=True)
    last_number = db.Column(db.Integer, nullable=False, default=0)


class Bill(db.Model):
    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(128))
    customer_phone = db.Column(db.String(20), index=True)
    bill_date = db.Column(db.DateTime, nullable=False, default=utcnow)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(16), nullable=False, default="cash")
    status = db.Column(db.String(16), nullable=False, default=BILL_COMPLETED, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    line_items = db.relationship("BillLineItem", backref="bill", lazy="joined", order_by="BillLineItem.id")
    creator = db.relationship("User")


class BillLineItem(db.Model):
    __tablename__ = "bill_line_items"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    product_name = db.Column(db.String(255), nullable=False)  # snapshot incl. brand/size
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)  # snapshot
    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Numeric(12, 2), nullable=False)
    returned_qty = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product")


class PurchaseInvoice(db.Model):
    __tablename__ = "purchase_invoices"

    id = db.Column(db.Integer, primary_key=True)
    supplier_name = db.Column(db.String(128), nullable=False)
    supplier_invoice_number = db.Column(db.String(64), nullable=False, index=True)
    purchase_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Numeric(12, 2))
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    line_items = db.relationship("PurchaseLineItem", backref="purchase_invoice", lazy="joined")
    creator = db.relationship("User")


class PurchaseLineItem(db.Model):
    __tablename__ = "purchase_line_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_invoice_id = db.Column(db.Integer, db.ForeignKey("purchase_invoices.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2))
    line_total = db.Column(db.Numeric(12, 2))

    product = db.relationship("Product")


class AppSetting(db.Model):
    """Key/value store for shop details shown on invoices and app config."""

    __tablename__ = "app_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")

    DEFAULTS = {
        "shop_name": "My Furniture Mart",
        "shop_address": "",
        "shop_phone": "",
        "shop_gstin": "",
        "currency_symbol": "₹",
        "invoice_footer": "Thank you for your business!",
    }

    @classmethod
    def get(cls, key):
        row = db.session.get(cls, key)
        if row is not None:
            return row.value
        return cls.DEFAULTS.get(key, "")

    @classmethod
    def set(cls, key, value):
        row = db.session.get(cls, key)
        if row is None:
            row = cls(key=key, value=value)
            db.session.add(row)
        else:
            row.value = value

    @classmethod
    def all_settings(cls):
        return {k: cls.get(k) for k in cls.DEFAULTS}


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref="push_subscriptions")
