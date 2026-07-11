from datetime import date
from decimal import Decimal

from app.models import User
from app.utils import amount_in_words


def test_amount_in_words():
    assert amount_in_words(Decimal("3150")) == "Three Thousand One Hundred and Fifty Only"
    assert amount_in_words(Decimal("0")) == "Zero Only"
    assert amount_in_words(Decimal("125.50")) == "One Hundred and Twenty Five and Fifty Paise Only"
    assert amount_in_words(Decimal("250000")) == "Two Lakh Fifty Thousand Only"
    assert amount_in_words(Decimal("10000000")) == "One Crore Only"


def test_register_requires_admin_approval(client, users, db):
    resp = client.post(
        "/auth/register",
        data={"username": "newstaff", "password": "secret6", "confirm": "secret6"},
        follow_redirects=True,
    )
    assert b"admin must approve" in resp.data

    user = User.query.filter_by(username="newstaff").one()
    assert user.role == "staff" and not user.is_approved

    # cannot log in yet
    resp = client.post(
        "/auth/login", data={"username": "newstaff", "password": "secret6"}, follow_redirects=True
    )
    assert b"awaiting admin approval" in resp.data

    # admin approves
    admin_login = client.post(
        "/auth/login", data={"username": "admin", "password": "adminpass"}, follow_redirects=True
    )
    assert admin_login.status_code == 200
    resp = client.post(f"/auth/users/{user.id}/approve", follow_redirects=True)
    assert b"approved" in resp.data
    client.get("/auth/logout")

    # now login works
    resp = client.post(
        "/auth/login", data={"username": "newstaff", "password": "secret6"}, follow_redirects=True
    )
    assert b"Billing" in resp.data


def test_register_duplicate_username(client, users):
    resp = client.post(
        "/auth/register",
        data={"username": "admin", "password": "secret6", "confirm": "secret6"},
        follow_redirects=True,
    )
    assert b"taken" in resp.data


def test_staff_cannot_approve(staff_client, users, db):
    pending = User(username="p1", role="staff", is_approved=False)
    pending.set_password("secret6")
    db.session.add(pending)
    db.session.commit()
    assert staff_client.post(f"/auth/users/{pending.id}/approve").status_code == 403


def test_invoice_shows_gst_split_and_hsn(admin_client, users, products, db):
    from app.services import billing_service, stock_service

    chair = products["chair"]
    chair.hsn_code = "9401"
    stock_service.create_purchase(
        {"supplier_name": "S", "supplier_invoice_number": "S-2", "purchase_date": date(2026, 7, 1)},
        [{"product": chair, "quantity": 5, "unit_cost": None}],
        users["admin"].id,
    )
    bill = billing_service.create_bill(
        {"tax_rate": Decimal("18"), "tax_amount": Decimal("180"), "customer_name": "Sravya"},
        [{"product": chair, "quantity": 2}],
        users["admin"].id,
    )
    assert bill.line_items[0].hsn_code == "9401"
    page = admin_client.get(f"/billing/bill/{bill.id}").data.decode()
    assert "CGST (9%)" in page and "SGST (9%)" in page
    assert "9401" in page
    assert "In Words:" in page
    assert "One Thousand One Hundred and Eighty Only" in page  # 1000 + 180
