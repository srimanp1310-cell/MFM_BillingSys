from datetime import date
from decimal import Decimal

import pytest

from app.models import Product, PurchaseInvoice, StockMovement
from app.services import stock_service


def ledger_sum(db, product):
    return (
        db.session.query(db.func.coalesce(db.func.sum(StockMovement.change_qty), 0))
        .filter_by(product_id=product.id)
        .scalar()
    )


HEADER = {
    "supplier_name": "Balaji Traders",
    "supplier_invoice_number": "BT-1",
    "purchase_date": date(2026, 7, 1),
}


def test_purchase_increments_stock_and_ledger(db, users, products):
    chair, bed = products["chair"], products["bed"]
    invoice = stock_service.create_purchase(
        HEADER,
        [
            {"product": chair, "quantity": 10, "unit_cost": Decimal("350")},
            {"product": bed, "quantity": 3, "unit_cost": None},
        ],
        users["admin"].id,
    )
    assert chair.quantity_on_hand == 10 == ledger_sum(db, chair)
    assert bed.quantity_on_hand == 3 == ledger_sum(db, bed)
    assert chair.cost_price == Decimal("350")
    assert bed.cost_price is None
    assert invoice.total_amount == Decimal("3500")
    movement = StockMovement.query.filter_by(product_id=chair.id).one()
    assert movement.movement_type == "PURCHASE"
    assert movement.reference_type == "purchase"
    assert movement.reference_id == invoice.id


def test_purchase_rolls_back_completely_on_bad_line(db, users, products):
    chair, bed = products["chair"], products["bed"]
    with pytest.raises(ValueError):
        stock_service.create_purchase(
            HEADER,
            [
                {"product": chair, "quantity": 5, "unit_cost": None},
                {"product": bed, "quantity": 0, "unit_cost": None},  # invalid
            ],
            users["admin"].id,
        )
    assert chair.quantity_on_hand == 0
    assert ledger_sum(db, chair) == 0
    assert PurchaseInvoice.query.count() == 0
    assert StockMovement.query.count() == 0


def test_purchase_requires_lines(users):
    with pytest.raises(ValueError):
        stock_service.create_purchase(HEADER, [], users["admin"].id)


def test_adjustment_requires_note(db, users, products):
    chair = products["chair"]
    with pytest.raises(ValueError):
        stock_service.adjust_stock(chair, -1, "   ", users["admin"].id)
    with pytest.raises(ValueError):
        stock_service.adjust_stock(chair, 0, "zero change", users["admin"].id)
    stock_service.adjust_stock(chair, -2, "damaged", users["admin"].id)
    assert chair.quantity_on_hand == -2 == ledger_sum(db, chair)


def test_recompute_fixes_drift(db, users, products):
    chair = products["chair"]
    stock_service.create_purchase(
        HEADER, [{"product": chair, "quantity": 8, "unit_cost": None}], users["admin"].id
    )
    chair.quantity_on_hand = 42  # simulate drift
    db.session.commit()
    drifted = stock_service.recompute_from_ledger()
    assert len(drifted) == 1
    assert drifted[0]["cached"] == 42 and drifted[0]["ledger"] == 8
    assert chair.quantity_on_hand == 8
    assert stock_service.recompute_from_ledger() == []


def test_low_stock_products(db, users, products):
    chair, bed = products["chair"], products["bed"]  # reorder levels 5 and 2
    stock_service.create_purchase(
        HEADER,
        [{"product": chair, "quantity": 10, "unit_cost": None},
         {"product": bed, "quantity": 2, "unit_cost": None}],
        users["admin"].id,
    )
    low = stock_service.low_stock_products()
    assert low == [bed]  # bed at reorder level; chair above
