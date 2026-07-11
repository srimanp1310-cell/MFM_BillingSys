def test_login_required_redirects(client):
    for url in ["/", "/billing/", "/history/", "/stock/", "/purchases/"]:
        resp = client.get(url)
        assert resp.status_code == 302, url
        assert "/auth/login" in resp.headers["Location"]


def test_wrong_password_rejected(client, users):
    resp = client.post(
        "/auth/login", data={"username": "admin", "password": "nope"}, follow_redirects=True
    )
    assert b"Invalid username or password" in resp.data


def test_inactive_user_cannot_login(client, users, db):
    users["staff"].is_active_flag = False
    db.session.commit()
    resp = client.post(
        "/auth/login", data={"username": "staff", "password": "staffpass"}, follow_redirects=True
    )
    assert b"Invalid username or password" in resp.data


def test_staff_blocked_from_admin_areas(staff_client):
    for url in ["/admin/", "/admin/products", "/admin/settings", "/auth/users"]:
        assert staff_client.get(url).status_code == 403, url
    assert staff_client.post("/admin/recompute").status_code == 403


def test_staff_can_use_daily_tabs(staff_client, products):
    for url in ["/billing/", "/history/", "/stock/", "/purchases/", "/purchases/new"]:
        assert staff_client.get(url).status_code == 200, url


def test_admin_can_reach_admin_areas(admin_client):
    for url in ["/admin/", "/admin/products", "/admin/settings", "/auth/users"]:
        assert admin_client.get(url).status_code == 200, url


def test_bill_save_via_http_and_reprint(admin_client, users, products, db):
    from datetime import date
    from decimal import Decimal

    from app.services import stock_service

    stock_service.create_purchase(
        {"supplier_name": "S", "supplier_invoice_number": "S-9", "purchase_date": date(2026, 7, 1)},
        [{"product": products["chair"], "quantity": 5, "unit_cost": Decimal("300")}],
        users["admin"].id,
    )
    resp = admin_client.post(
        "/billing/save",
        data={
            "customer_name": "Meena",
            "payment_method": "card",
            "bill_number": "",
            "product_id[]": [str(products["chair"].id)],
            "quantity[]": ["2"],
            "unit_price[]": [""],
            "discount": "50",
            "apply_tax": "1",
            "tax_mode": "percent",
            "tax_value": "18",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200 and b"saved" in resp.data
    from app.models import Bill

    bill = Bill.query.one()
    assert bill.subtotal == Decimal("1000.00")
    assert bill.tax_amount == Decimal("171.00")  # (1000-50) * 18%
    assert bill.total == Decimal("1121.00")
    view = admin_client.get(f"/billing/bill/{bill.id}")
    assert view.status_code == 200 and bill.bill_number.encode() in view.data
