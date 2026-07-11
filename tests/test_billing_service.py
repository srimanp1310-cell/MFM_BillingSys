from datetime import date
from decimal import Decimal

import pytest

from app.models import Bill, StockMovement
from app.services import billing_service, stock_service


@pytest.fixture()
def stocked(db, users, products):
    stock_service.create_purchase(
        {"supplier_name": "S", "supplier_invoice_number": "S-1", "purchase_date": date(2026, 7, 1)},
        [{"product": products["chair"], "quantity": 10, "unit_cost": Decimal("350")},
         {"product": products["bed"], "quantity": 5, "unit_cost": Decimal("6000")}],
        users["admin"].id,
    )
    return products


def make_bill(users, product, qty=2, **header):
    return billing_service.create_bill(
        {"payment_method": "cash", **header},
        [{"product": product, "quantity": qty}],
        users["admin"].id,
    )


def test_bill_decrements_stock_and_snapshots(db, users, stocked):
    chair = stocked["chair"]
    bill = billing_service.create_bill(
        {"customer_name": "Ravi", "discount": Decimal("100"), "tax_amount": Decimal("90")},
        [{"product": chair, "quantity": 2},
         {"product": stocked["bed"], "quantity": 1, "unit_price": Decimal("7500")}],
        users["admin"].id,
    )
    assert chair.quantity_on_hand == 8
    assert bill.subtotal == Decimal("500") * 2 + Decimal("7500")
    assert bill.total == bill.subtotal - Decimal("100") + Decimal("90")
    li_bed = bill.line_items[1]
    assert li_bed.unit_price == Decimal("7500")  # negotiated price snapshot
    assert "Ortho Mattress" in li_bed.product_name and "(72x36)" in li_bed.product_name
    sale = StockMovement.query.filter_by(product_id=chair.id, movement_type="SALE").one()
    assert sale.change_qty == -2 and sale.reference_id == bill.id


def test_negative_stock_allowed(db, users, stocked):
    chair = stocked["chair"]
    make_bill(users, chair, qty=15)  # only 10 in stock — warn-and-allow policy
    assert chair.quantity_on_hand == -5


def test_sequential_numbering_and_manual_override(db, users, stocked):
    chair = stocked["chair"]
    b1 = make_bill(users, chair, qty=1)
    b2 = make_bill(users, chair, qty=1)
    year = b1.bill_number.split("-")[1]
    assert b1.bill_number.endswith("0001") and b2.bill_number.endswith("0002")

    manual = make_bill(users, chair, qty=1, bill_number="CUSTOM-77")
    assert manual.bill_number == "CUSTOM-77"
    # manual numbers don't disturb the auto sequence
    b3 = make_bill(users, chair, qty=1)
    assert b3.bill_number == f"INV-{year}-0003"

    with pytest.raises(ValueError, match="already exists"):
        make_bill(users, chair, qty=1, bill_number="CUSTOM-77")


def test_failed_bill_rolls_back_and_keeps_numbering_gap_free(db, users, stocked):
    chair, bed = stocked["chair"], stocked["bed"]
    b1 = make_bill(users, chair, qty=1)
    with pytest.raises(ValueError):
        billing_service.create_bill(
            {},
            [{"product": chair, "quantity": 1}, {"product": bed, "quantity": 0}],
            users["admin"].id,
        )
    assert chair.quantity_on_hand == 9  # only the first bill's decrement
    assert Bill.query.count() == 1
    b2 = make_bill(users, chair, qty=1)
    # the failed attempt must not burn a number
    n1 = int(b1.bill_number.rsplit("-", 1)[1])
    n2 = int(b2.bill_number.rsplit("-", 1)[1])
    assert n2 == n1 + 1


def test_discount_validation(users, stocked):
    with pytest.raises(ValueError, match="Discount"):
        make_bill(users, stocked["chair"], qty=1, discount=Decimal("9999"))


def test_void_restores_stock_once(db, users, stocked):
    chair = stocked["chair"]
    bill = make_bill(users, chair, qty=4)
    assert chair.quantity_on_hand == 6
    billing_service.void_bill(bill, users["admin"].id)
    assert bill.status == "voided"
    assert chair.quantity_on_hand == 10
    reversal = StockMovement.query.filter_by(movement_type="VOID_REVERSAL").one()
    assert reversal.change_qty == 4
    with pytest.raises(ValueError, match="already voided"):
        billing_service.void_bill(bill, users["admin"].id)


def test_return_partial_and_limits(db, users, stocked):
    chair = stocked["chair"]
    bill = make_bill(users, chair, qty=4)
    li = bill.line_items[0]
    stock_service.record_return(bill, {li.id: 1}, "changed mind", users["admin"].id)
    assert chair.quantity_on_hand == 7 and li.returned_qty == 1
    with pytest.raises(ValueError, match="only 3 left"):
        stock_service.record_return(bill, {li.id: 4}, None, users["admin"].id)
    with pytest.raises(ValueError, match="at least one"):
        stock_service.record_return(bill, {li.id: 0}, None, users["admin"].id)


def test_void_after_partial_return_only_reverses_remainder(db, users, stocked):
    chair = stocked["chair"]
    bill = make_bill(users, chair, qty=4)  # 10 -> 6
    li = bill.line_items[0]
    stock_service.record_return(bill, {li.id: 1}, "r", users["admin"].id)  # 6 -> 7
    billing_service.void_bill(bill, users["admin"].id)  # should add only 3
    assert chair.quantity_on_hand == 10  # not 11
