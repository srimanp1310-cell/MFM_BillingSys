"""Single audited, transactional code path for every stock mutation.

Rules (PROJECT_BRIEF §6):
- every change writes a StockMovement AND updates Product.quantity_on_hand
- callers get atomicity: each public function commits on success and rolls
  back on any failure, so stock and records never drift apart.
"""

from decimal import Decimal

from app.extensions import db
from app.models import (
    MOVE_ADJUSTMENT,
    MOVE_PURCHASE,
    MOVE_RETURN,
    MOVE_VOID_REVERSAL,
    Product,
    PurchaseInvoice,
    PurchaseLineItem,
    StockMovement,
)


def apply_movement(product, change_qty, movement_type, user_id, reference_type=None, reference_id=None, note=None):
    """Add one ledger entry and update the cached quantity. No commit — the
    caller owns the transaction."""
    movement = StockMovement(
        product_id=product.id,
        change_qty=change_qty,
        movement_type=movement_type,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        created_by=user_id,
    )
    db.session.add(movement)
    product.quantity_on_hand += change_qty
    return movement


def create_purchase(header, lines, user_id):
    """Record a purchase invoice and increment stock for each line.

    header: dict(supplier_name, supplier_invoice_number, purchase_date, note)
    lines:  list of dict(product, quantity, unit_cost) — product may be a
            not-yet-flushed Product created inline by the caller (same session).
    """
    if not lines:
        raise ValueError("A purchase needs at least one line item.")
    try:
        invoice = PurchaseInvoice(
            supplier_name=header["supplier_name"],
            supplier_invoice_number=header["supplier_invoice_number"],
            purchase_date=header["purchase_date"],
            note=header.get("note"),
            created_by=user_id,
        )
        db.session.add(invoice)
        db.session.flush()  # assigns invoice.id and ids of inline products

        total = Decimal("0")
        for line in lines:
            product = line["product"]
            qty = int(line["quantity"])
            if qty <= 0:
                raise ValueError(f"Quantity for {product.name} must be positive.")
            unit_cost = line.get("unit_cost")
            line_total = (unit_cost * qty) if unit_cost is not None else None
            db.session.add(
                PurchaseLineItem(
                    purchase_invoice_id=invoice.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_cost=unit_cost,
                    line_total=line_total,
                )
            )
            apply_movement(
                product, qty, MOVE_PURCHASE, user_id, reference_type="purchase", reference_id=invoice.id
            )
            if unit_cost is not None:
                product.cost_price = unit_cost
            if line_total is not None:
                total += line_total

        invoice.total_amount = total if total else None
        db.session.commit()
        return invoice
    except Exception:
        db.session.rollback()
        raise


def adjust_stock(product, change_qty, note, user_id):
    """Manual correction (damage, miscount...). Note is mandatory. Admin-only
    (enforced at the route)."""
    if not note or not note.strip():
        raise ValueError("An adjustment requires a note explaining why.")
    if change_qty == 0:
        raise ValueError("Adjustment quantity cannot be zero.")
    try:
        movement = apply_movement(product, change_qty, MOVE_ADJUSTMENT, user_id, note=note.strip())
        db.session.commit()
        return movement
    except Exception:
        db.session.rollback()
        raise


def record_return(bill, quantities, note, user_id):
    """Minimal return flow: restore stock for selected bill lines.

    quantities: dict {bill_line_item_id: qty_to_return}
    """
    from app.models import BILL_COMPLETED

    if bill.status != BILL_COMPLETED:
        raise ValueError("Only completed bills can have returns.")
    lines_by_id = {li.id: li for li in bill.line_items}
    to_return = [(lines_by_id[i], q) for i, q in quantities.items() if q > 0 and i in lines_by_id]
    if not to_return:
        raise ValueError("Select at least one item to return.")
    try:
        for line, qty in to_return:
            returnable = line.quantity - line.returned_qty
            if qty > returnable:
                raise ValueError(
                    f"Cannot return {qty} of {line.product_name}: only {returnable} left on this bill."
                )
            apply_movement(
                line.product,
                qty,
                MOVE_RETURN,
                user_id,
                reference_type="bill",
                reference_id=bill.id,
                note=note or f"Return against {bill.bill_number}",
            )
            line.returned_qty += qty
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def reverse_bill_stock(bill, user_id):
    """Insert VOID_REVERSAL movements for a bill being voided. No commit —
    called from billing_service.void_bill inside its transaction. Quantities
    already returned are not reversed again."""
    for line in bill.line_items:
        remaining = line.quantity - line.returned_qty
        if remaining > 0:
            apply_movement(
                line.product,
                remaining,
                MOVE_VOID_REVERSAL,
                user_id,
                reference_type="bill",
                reference_id=bill.id,
                note=f"Void of {bill.bill_number}",
            )


def recompute_from_ledger():
    """Safety net: rebuild every product's quantity_on_hand from the ledger.
    Returns a list of dicts for products whose cache had drifted."""
    drifted = []
    try:
        products = Product.query.all()
        for product in products:
            ledger_sum = (
                db.session.query(db.func.coalesce(db.func.sum(StockMovement.change_qty), 0))
                .filter(StockMovement.product_id == product.id)
                .scalar()
            )
            if ledger_sum != product.quantity_on_hand:
                drifted.append(
                    {"product": product, "cached": product.quantity_on_hand, "ledger": ledger_sum}
                )
                product.quantity_on_hand = ledger_sum
        db.session.commit()
        return drifted
    except Exception:
        db.session.rollback()
        raise


def low_stock_products():
    return (
        Product.query.filter(
            Product.is_active.is_(True),
            Product.reorder_level.isnot(None),
            Product.quantity_on_hand <= Product.reorder_level,
        )
        .order_by(Product.name)
        .all()
    )
