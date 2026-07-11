"""Bill creation, numbering, and voiding — all transactional."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    BILL_COMPLETED,
    BILL_VOIDED,
    MOVE_SALE,
    Bill,
    BillLineItem,
    BillSequence,
)
from app.services.stock_service import apply_movement, reverse_bill_stock
from app.utils import local_now


def next_bill_number():
    """Gap-free sequential number per (local) year, safe under concurrency.

    Locks the year's BillSequence row (SELECT ... FOR UPDATE on Postgres;
    SQLite serializes writers anyway). Must be called inside the same
    transaction that saves the bill so a rollback releases the number.
    """
    year = local_now().year
    seq = db.session.execute(
        select(BillSequence).where(BillSequence.year == year).with_for_update()
    ).scalar_one_or_none()
    if seq is None:
        seq = BillSequence(year=year, last_number=0)
        db.session.add(seq)
        db.session.flush()
    seq.last_number += 1
    return f"INV-{year}-{seq.last_number:04d}"


def create_bill(header, lines, user_id):
    """Persist a bill, snapshot line items, and decrement stock — one transaction.

    header: dict(bill_number(optional manual), customer_name, customer_phone,
                 discount, tax_amount, payment_method)
    lines:  list of dict(product, quantity)  — unit price is snapshotted from
            the product unless an overridden 'unit_price' is provided.
    """
    if not lines:
        raise ValueError("A bill needs at least one line item.")

    manual_number = (header.get("bill_number") or "").strip()
    attempts = 2  # retry once if two first-bills-of-the-year race on the sequence row
    for attempt in range(attempts):
        try:
            bill_number = manual_number or next_bill_number()
            if Bill.query.filter_by(bill_number=bill_number).first():
                raise ValueError(f"Bill number '{bill_number}' already exists.")

            subtotal = Decimal("0")
            bill = Bill(
                bill_number=bill_number,
                customer_name=header.get("customer_name") or None,
                customer_phone=header.get("customer_phone") or None,
                discount=header.get("discount") or Decimal("0"),
                tax_rate=header.get("tax_rate"),
                tax_amount=header.get("tax_amount") or Decimal("0"),
                payment_method=header.get("payment_method") or "cash",
                status=BILL_COMPLETED,
                created_by=user_id,
            )
            db.session.add(bill)
            db.session.flush()

            for line in lines:
                product = line["product"]
                qty = int(line["quantity"])
                if qty <= 0:
                    raise ValueError(f"Quantity for {product.name} must be positive.")
                unit_price = line.get("unit_price")
                if unit_price is None:
                    unit_price = product.unit_price
                line_total = unit_price * qty
                subtotal += line_total
                db.session.add(
                    BillLineItem(
                        bill_id=bill.id,
                        product_id=product.id,
                        product_name=product.display_name,  # snapshot
                        hsn_code=product.hsn_code,  # snapshot
                        unit_price=unit_price,  # snapshot
                        quantity=qty,
                        line_total=line_total,
                    )
                )
                apply_movement(
                    product, -qty, MOVE_SALE, user_id, reference_type="bill", reference_id=bill.id
                )

            discount = bill.discount or Decimal("0")
            if discount < 0 or discount > subtotal:
                raise ValueError("Discount must be between 0 and the subtotal.")
            bill.subtotal = subtotal
            bill.total = subtotal - discount + (bill.tax_amount or Decimal("0"))
            db.session.commit()
            return bill
        except IntegrityError:
            db.session.rollback()
            if attempt == attempts - 1:
                raise
        except Exception:
            db.session.rollback()
            raise


def void_bill(bill, user_id):
    """Mark voided (never delete) and restore stock. Admin-only at the route."""
    if bill.status == BILL_VOIDED:
        raise ValueError("This bill is already voided.")
    try:
        bill.status = BILL_VOIDED
        reverse_bill_stock(bill, user_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
